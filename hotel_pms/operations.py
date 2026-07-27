from __future__ import annotations

import json
from datetime import datetime

import frappe
from frappe import _
from frappe.exceptions import DuplicateEntryError
from frappe.utils import add_to_date, cint, flt, get_datetime, getdate, now_datetime, nowdate

from hotel_pms.notifications import notify_roles, notify_users
from hotel_pms.operations_rules import calculate_inspection_result, calculate_sla_status, elapsed_minutes, should_create_sop_candidate
from hotel_pms.room_status import expected_operational_status, restore_room_after_engineering, set_room_status
from hotel_pms.sync import make_sync_key

HK_STAFF_ROLES = {"Housekeeping", "Housekeeping Supervisor", "Hotel Manager", "System Manager"}
HK_SUPERVISOR_ROLES = {"Housekeeping Supervisor", "Hotel Manager", "System Manager"}
ENGINEERING_ROLES = {"Engineering", "Engineering Supervisor", "Hotel Manager", "System Manager"}
ENGINEERING_SUPERVISOR_ROLES = {"Engineering Supervisor", "Hotel Manager", "System Manager"}
FRONT_DESK_ROLES = {"Front Desk", "Hotel Manager", "System Manager"}


def _roles() -> set[str]:
    return set(frappe.get_roles())


def _require_any(roles: set[str]) -> None:
    if not (_roles() & roles):
        frappe.throw(_("You do not have permission for this hotel operation."), frappe.PermissionError)


def _parse(value):
    if isinstance(value, str):
        return frappe.parse_json(value)
    return value or {}


def _lock(doctype: str, name: str):
    rows = frappe.db.sql(f"select name from `tab{doctype}` where name=%s for update", name, as_dict=True)
    if not rows:
        frappe.throw(_("{0} {1} was not found.").format(doctype, name))
    return frappe.get_doc(doctype, name)


def _can_operate_task(doc) -> None:
    _require_any(HK_STAFF_ROLES)
    if doc.assigned_to and doc.assigned_to != frappe.session.user and not (_roles() & HK_SUPERVISOR_ROLES):
        frappe.throw(_("This task is assigned to {0}.").format(doc.assigned_to))


def _append_hk_log(doc, action: str, reason: str | None = None) -> None:
    doc.append(
        "time_logs",
        {
            "event_at": now_datetime(),
            "action": action,
            "user": frappe.session.user,
            "reason": reason,
            "elapsed_minutes": doc.cleaning_minutes or 0,
        },
    )


def _append_maintenance_log(doc, action: str, notes: str | None = None, material_summary: str | None = None) -> None:
    doc.append(
        "work_logs",
        {
            "event_at": now_datetime(),
            "action": action,
            "user": frappe.session.user,
            "notes": notes,
            "material_summary": material_summary,
        },
    )


def _turnaround_minutes(doc, ready_at) -> float:
    if not doc.reservation:
        return 0
    checkout_at = frappe.db.get_value("Hotel Reservation", doc.reservation, "actual_check_out_at")
    return elapsed_minutes(get_datetime(checkout_at) if checkout_at else None, get_datetime(ready_at), 0)


@frappe.whitelist()
def mark_guest_waiting(task: str, waiting: int = 1) -> dict:
    _require_any(FRONT_DESK_ROLES | HK_SUPERVISOR_ROLES)
    doc = _lock("Hotel Housekeeping Task", task)
    doc.guest_waiting = cint(waiting)
    doc._set_next_arrival_and_priority()
    doc.save(ignore_permissions=True)
    notify_roles(
        ["Housekeeping", "Housekeeping Supervisor", "Hotel Manager"],
        property_name=doc.property,
        subject=_("Guest waiting for room {0}").format(doc.room) if doc.guest_waiting else _("Guest-waiting flag cleared for room {0}").format(doc.room),
        message=_("Housekeeping task {0} priority is now {1}.").format(doc.name, doc.priority),
        document_type=doc.doctype,
        document_name=doc.name,
        dedupe_key=f"guest-waiting:{doc.name}:{doc.guest_waiting}:{doc.modified}",
    )
    return {"task": doc.name, "guest_waiting": doc.guest_waiting, "priority": doc.priority, "priority_score": doc.priority_score}


@frappe.whitelist()
def get_housekeeping_queue(property: str | None = None, assigned_only: int = 0, include_completed: int = 0) -> dict:
    _require_any(HK_STAFF_ROLES | FRONT_DESK_ROLES | ENGINEERING_ROLES)
    property = property or frappe.db.get_single_value("Hotel PMS Settings", "default_property")
    filters = ["h.task_date <= %(today)s"]
    params = {"today": getdate(), "property": property, "user": frappe.session.user}
    if property:
        filters.append("h.property=%(property)s")
    if not cint(include_completed):
        filters.append("h.status not in ('Completed','Cancelled')")
    if cint(assigned_only):
        filters.append("(h.assigned_to=%(user)s or h.assigned_to is null or h.assigned_to='')")
    rows = frappe.db.sql(
        f"""
        select h.name, h.property, h.room, r.room_number, r.room_type, r.floor,
               h.reservation, h.maintenance_ticket, h.task_type, h.status, h.priority,
               h.priority_score, h.guest_waiting, h.assigned_to, h.started_at, h.paused_at,
               h.next_arrival_at, h.target_ready_at, h.cleaning_minutes, h.total_pause_minutes,
               r.operational_status, r.housekeeping_status
        from `tabHotel Housekeeping Task` h
        inner join `tabHotel Room` r on r.name=h.room
        where {' and '.join(filters)}
        order by h.priority_score desc, h.target_ready_at asc, h.creation asc
        """,
        params,
        as_dict=True,
    )
    metrics = {
        "open": sum(1 for row in rows if row.status == "Open"),
        "assigned": sum(1 for row in rows if row.status == "Assigned"),
        "in_progress": sum(1 for row in rows if row.status == "In Progress"),
        "paused": sum(1 for row in rows if row.status in ("Paused", "Waiting Engineering")),
        "inspection": sum(1 for row in rows if row.status == "Ready for Inspection"),
        "reclean": sum(1 for row in rows if row.status == "Reclean Required"),
    }
    return {"property": property, "tasks": rows, "metrics": metrics, "server_time": now_datetime()}


@frappe.whitelist()
def get_housekeeping_task(task: str) -> dict:
    _require_any(HK_STAFF_ROLES | FRONT_DESK_ROLES | ENGINEERING_ROLES)
    doc = frappe.get_doc("Hotel Housekeeping Task", task)
    doc.check_permission("read")
    return doc.as_dict()


@frappe.whitelist()
def assign_housekeeping_task(task: str, assigned_to: str, idempotency_key: str | None = None) -> dict:
    _require_any(HK_SUPERVISOR_ROLES)
    doc = _lock("Hotel Housekeeping Task", task)
    if doc.status in ("Completed", "Cancelled"):
        frappe.throw(_("Completed or cancelled tasks cannot be reassigned."))
    if doc.assigned_to == assigned_to and doc.status in ("Assigned", "In Progress", "Paused", "Waiting Engineering"):
        return {"task": doc.name, "already_processed": True}
    if not frappe.db.get_value("User", assigned_to, "enabled"):
        frappe.throw(_("Assigned user is disabled or missing."))
    user_roles = set(frappe.get_roles(assigned_to))
    if not (user_roles & {"Housekeeping", "Housekeeping Supervisor", "Hotel Manager", "System Manager"}):
        frappe.throw(_("Assigned user does not have a housekeeping role."))
    doc.assigned_to = assigned_to
    doc.assigned_at = now_datetime()
    if doc.status in ("Open", "Reclean Required"):
        doc.status = "Assigned"
    _append_hk_log(doc, "Assigned", f"Assigned to {assigned_to}")
    doc.save(ignore_permissions=True)
    set_room_status(
        doc.room,
        housekeeping_status="Assigned",
        event_type="Housekeeping Assigned",
        source_doctype=doc.doctype,
        source_name=doc.name,
        idempotency_key=idempotency_key or f"assign:{doc.name}:{assigned_to}",
    )
    notify_users(
        [assigned_to],
        subject=_("Room {0} assigned for cleaning").format(doc.room),
        message=_("Task {0}: {1}. Target ready: {2}").format(doc.name, doc.task_type, doc.target_ready_at or "-"),
        document_type=doc.doctype,
        document_name=doc.name,
        dedupe_key=idempotency_key or f"hk-assign:{doc.name}:{assigned_to}",
    )
    return {"task": doc.name, "assigned_to": assigned_to, "already_processed": False}


@frappe.whitelist()
def start_housekeeping_task(task: str) -> dict:
    doc = _lock("Hotel Housekeeping Task", task)
    _can_operate_task(doc)
    if doc.status == "In Progress":
        return {"task": doc.name, "already_processed": True}
    if doc.status not in ("Open", "Assigned", "Reclean Required"):
        frappe.throw(_("Task status {0} cannot be started.").format(doc.status))
    if not doc.assigned_to:
        doc.assigned_to = frappe.session.user
        doc.assigned_at = now_datetime()
        _append_hk_log(doc, "Assigned", "Self-assigned on start")
    doc.accepted_at = doc.accepted_at or now_datetime()
    doc.started_at = doc.started_at or now_datetime()
    if doc.paused_at:
        doc.total_pause_minutes = flt(doc.total_pause_minutes) + max((now_datetime() - get_datetime(doc.paused_at)).total_seconds() / 60, 0)
    doc.paused_at = None
    doc.pause_reason = None
    doc.status = "In Progress"
    _append_hk_log(doc, "Started")
    doc.save(ignore_permissions=True)
    set_room_status(
        doc.room,
        housekeeping_status="Cleaning",
        event_type="Cleaning Started",
        source_doctype=doc.doctype,
        source_name=doc.name,
        idempotency_key=f"start:{doc.name}:{len(doc.time_logs)}",
    )
    return {"task": doc.name, "status": doc.status, "started_at": doc.started_at, "already_processed": False}


@frappe.whitelist()
def pause_housekeeping_task(task: str, reason: str, waiting_engineering: int = 0) -> dict:
    if not reason:
        frappe.throw(_("Pause reason is required."))
    doc = _lock("Hotel Housekeeping Task", task)
    _can_operate_task(doc)
    if doc.status not in ("In Progress",):
        frappe.throw(_("Only an in-progress task can be paused."))
    doc.paused_at = now_datetime()
    doc.pause_reason = reason
    doc.status = "Waiting Engineering" if cint(waiting_engineering) else "Paused"
    _append_hk_log(doc, "Paused", reason)
    doc.save(ignore_permissions=True)
    set_room_status(
        doc.room,
        housekeeping_status="Waiting Engineering" if cint(waiting_engineering) else "Cleaning",
        event_type="Cleaning Paused",
        source_doctype=doc.doctype,
        source_name=doc.name,
        notes=reason,
        idempotency_key=f"pause:{doc.name}:{len(doc.time_logs)}",
    )
    return {"task": doc.name, "status": doc.status}


@frappe.whitelist()
def resume_housekeeping_task(task: str) -> dict:
    doc = _lock("Hotel Housekeeping Task", task)
    _can_operate_task(doc)
    if doc.status not in ("Paused", "Waiting Engineering"):
        frappe.throw(_("Only a paused task can be resumed."))
    if doc.paused_at:
        doc.total_pause_minutes = flt(doc.total_pause_minutes) + max(
            (now_datetime() - get_datetime(doc.paused_at)).total_seconds() / 60, 0
        )
    doc.paused_at = None
    doc.pause_reason = None
    doc.status = "In Progress"
    _append_hk_log(doc, "Resumed")
    doc.save(ignore_permissions=True)
    set_room_status(
        doc.room,
        housekeeping_status="Cleaning",
        event_type="Cleaning Resumed",
        source_doctype=doc.doctype,
        source_name=doc.name,
        idempotency_key=f"resume:{doc.name}:{len(doc.time_logs)}",
    )
    return {"task": doc.name, "status": doc.status, "pause_minutes": doc.total_pause_minutes}


@frappe.whitelist()
def update_housekeeping_checklist(task: str, row_name: str, result: str, notes: str | None = None, photo: str | None = None) -> dict:
    doc = _lock("Hotel Housekeeping Task", task)
    _can_operate_task(doc)
    if doc.status not in ("Assigned", "In Progress", "Paused", "Waiting Engineering", "Reclean Required"):
        frappe.throw(_("Checklist cannot be changed in status {0}.").format(doc.status))
    allowed = {"Pending", "OK", "Not OK", "Not Applicable", "Reported to Engineering"}
    if result not in allowed:
        frappe.throw(_("Invalid checklist result."))
    row = next((item for item in doc.checklist_items if item.name == row_name), None)
    if not row:
        frappe.throw(_("Checklist row was not found."))
    if result == "Reported to Engineering" and not notes:
        frappe.throw(_("Describe the defect before reporting it to Engineering."))
    row.result = result
    row.notes = notes
    if photo is not None:
        row.photo = photo
    doc.save(ignore_permissions=True)

    ticket = row.maintenance_ticket
    if result == "Reported to Engineering" and not ticket:
        response = report_maintenance_issue(
            {
                "property": doc.property,
                "room": doc.room,
                "reservation": doc.reservation,
                "housekeeping_task": doc.name,
                "checklist_row": row.name,
                "source": "Housekeeping",
                "subject": row.item_label,
                "problem_category": "Other",
                "description": notes,
                "priority": "High - Guest Visible" if row.is_critical else "Medium",
                "guest_impact": "Major Inconvenience" if row.is_critical else "Minor Inconvenience",
                "affects_room_sale": cint(row.is_critical),
                "before_photo": row.photo,
            },
            idempotency_key=f"CHECKLIST-{doc.name}-{row.name}",
        )
        ticket = response.get("ticket")
    return {"task": doc.name, "row": row.name, "result": row.result, "maintenance_ticket": ticket}


def _validate_cleaning_complete(doc) -> None:
    if cint(frappe.db.get_single_value("Hotel PMS Settings", "require_housekeeping_checklist")) and not doc.checklist_items:
        frappe.throw(_("A cleaning checklist is required. Configure an enabled checklist template for this property, room type, and task type."))
    incomplete = [row for row in doc.checklist_items if row.result in (None, "", "Pending")]
    failed = [row for row in doc.checklist_items if row.result in ("Not OK", "Reported to Engineering")]
    if incomplete:
        frappe.throw(_("Complete all checklist items before finishing the room."))
    if failed:
        frappe.throw(
            _("Resolve or mark non-applicable all failed checklist items before finishing. Outstanding: {0}").format(
                ", ".join(row.item_label for row in failed[:5])
            )
        )


@frappe.whitelist()
def complete_housekeeping_task(task: str, notes: str | None = None) -> dict:
    doc = _lock("Hotel Housekeeping Task", task)
    _can_operate_task(doc)
    if doc.status in ("Ready for Inspection", "Completed"):
        return {"task": doc.name, "status": doc.status, "already_processed": True}
    if doc.status != "In Progress":
        frappe.throw(_("Only an in-progress task can be completed."))
    _validate_cleaning_complete(doc)
    doc.completed_at = now_datetime()
    doc.cleaning_minutes = elapsed_minutes(get_datetime(doc.started_at), get_datetime(doc.completed_at), doc.total_pause_minutes or 0)
    if notes:
        doc.notes = notes
    require_inspection = cint(frappe.db.get_single_value("Hotel PMS Settings", "require_housekeeping_inspection"))
    doc.status = "Ready for Inspection" if require_inspection else "Completed"
    if require_inspection:
        doc.paused_at = doc.completed_at
        doc.pause_reason = "Waiting supervisor inspection"
    if not require_inspection:
        doc.inspected_at = doc.completed_at
        doc.inspected_by = frappe.session.user
        doc.first_pass = 1
        doc.turnaround_minutes = _turnaround_minutes(doc, doc.inspected_at)
    _append_hk_log(doc, "Completed", notes)
    doc.save(ignore_permissions=True)
    set_room_status(
        doc.room,
        housekeeping_status="Ready for Inspection" if require_inspection else "Inspected",
        event_type="Cleaning Completed" if require_inspection else "Room Ready",
        source_doctype=doc.doctype,
        source_name=doc.name,
        notes=notes,
        idempotency_key=f"complete:{doc.name}:{doc.completed_at}",
    )
    if require_inspection:
        notify_roles(
            ["Housekeeping Supervisor", "Hotel Manager"],
            property_name=doc.property,
            subject=_("Room {0} awaits housekeeping inspection").format(doc.room),
            message=_("{0} completed task {1} in {2} minutes.").format(doc.assigned_to or frappe.session.user, doc.name, doc.cleaning_minutes),
            document_type=doc.doctype,
            document_name=doc.name,
            dedupe_key=f"hk-inspection:{doc.name}:{doc.completed_at}",
        )
    else:
        _notify_room_ready(doc)
        _finish_post_maintenance_if_applicable(doc)
    return {"task": doc.name, "status": doc.status, "cleaning_minutes": doc.cleaning_minutes, "already_processed": False}


def _inspection_items(doc):
    return [
        {
            "area": row.area,
            "item_label": row.item_label,
            "result": "OK" if row.result == "OK" else row.result,
            "is_critical": row.is_critical,
            "weight": row.weight or 1,
            "notes": row.notes,
            "photo": row.photo,
        }
        for row in doc.checklist_items
    ]


@frappe.whitelist()
def inspect_housekeeping_task(task: str, decision: str, notes: str | None = None, idempotency_key: str | None = None) -> dict:
    _require_any(HK_SUPERVISOR_ROLES)
    doc = _lock("Hotel Housekeeping Task", task)
    if doc.status == "Completed" and doc.inspection:
        return {"task": doc.name, "inspection": doc.inspection, "status": doc.status, "already_processed": True}
    if doc.status != "Ready for Inspection":
        frappe.throw(_("Task is not ready for inspection."))
    template_pass_score = frappe.db.get_value("Hotel Cleaning Checklist Template", doc.checklist_template, "pass_score") if doc.checklist_template else 90
    items = _inspection_items(doc)
    requested_pass = decision == "Pass"
    if not requested_pass:
        items.append({
            "area": "Supervisor",
            "item_label": "Supervisor inspection finding",
            "result": "Not OK",
            "is_critical": 1,
            "weight": 1,
            "notes": notes or "Reclean required by supervisor.",
            "photo": None,
        })
    calculated = calculate_inspection_result(items, template_pass_score or 90)
    result = "Pass" if requested_pass and calculated.passed else "Reclean Required"
    key = make_sync_key("INSPECT", doc.name, idempotency_key or f"{now_datetime()}:{result}")
    existing = frappe.db.get_value("Hotel Room Inspection", {"idempotency_key": key}, "name")
    if existing:
        return {"task": doc.name, "inspection": existing, "already_processed": True}
    attempt = frappe.db.count("Hotel Room Inspection", {"housekeeping_task": doc.name}) + 1
    inspection = frappe.get_doc(
        {
            "doctype": "Hotel Room Inspection",
            "property": doc.property,
            "room": doc.room,
            "housekeeping_task": doc.name,
            "reservation": doc.reservation,
            "inspection_type": "Post-Maintenance Inspection" if doc.maintenance_ticket else "Cleaning Inspection",
            "attempt_no": attempt,
            "result": result,
            "score": calculated.score,
            "pass_score": template_pass_score or 90,
            "inspected_by": frappe.session.user,
            "inspected_at": now_datetime(),
            "idempotency_key": key,
            "notes": notes,
            "items": items,
        }
    ).insert(ignore_permissions=True)
    doc.inspection = inspection.name
    doc.inspected_at = inspection.inspected_at
    doc.inspected_by = inspection.inspected_by
    if result == "Pass":
        doc.status = "Completed"
        doc.paused_at = None
        doc.pause_reason = None
        doc.first_pass = 1 if attempt == 1 else 0
        doc.turnaround_minutes = _turnaround_minutes(doc, doc.inspected_at)
        _append_hk_log(doc, "Inspection Passed", notes)
        doc.save(ignore_permissions=True)
        set_room_status(
            doc.room,
            housekeeping_status="Inspected",
            event_type="Housekeeping Inspection Passed",
            source_doctype=inspection.doctype,
            source_name=inspection.name,
            notes=notes,
            idempotency_key=f"inspection-pass:{inspection.name}",
        )
        _notify_room_ready(doc)
        _finish_post_maintenance_if_applicable(doc)
    else:
        doc.status = "Reclean Required"
        doc.paused_at = doc.paused_at or inspection.inspected_at
        doc.pause_reason = notes or "Reclean required by supervisor"
        _append_hk_log(doc, "Reclean Required", notes)
        doc.save(ignore_permissions=True)
        set_room_status(
            doc.room,
            housekeeping_status="Reclean Required",
            event_type="Housekeeping Inspection Failed",
            source_doctype=inspection.doctype,
            source_name=inspection.name,
            notes=notes,
            idempotency_key=f"inspection-fail:{inspection.name}",
        )
        if doc.assigned_to:
            notify_users(
                [doc.assigned_to],
                subject=_("Room {0} requires reclean").format(doc.room),
                message=notes or _("Supervisor inspection did not pass. Open the task for details."),
                document_type=doc.doctype,
                document_name=doc.name,
                dedupe_key=f"hk-reclean:{inspection.name}",
            )
    return {"task": doc.name, "inspection": inspection.name, "status": doc.status, "score": calculated.score, "already_processed": False}


def _notify_room_ready(doc) -> None:
    notify_roles(
        ["Front Desk", "Hotel Manager"],
        property_name=doc.property,
        subject=_("Room {0} is ready").format(doc.room),
        message=_("Housekeeping task {0} is completed and the room is ready for sale or arrival.").format(doc.name),
        document_type="Hotel Room",
        document_name=doc.room,
        dedupe_key=f"room-ready:{doc.name}:{doc.inspected_at or doc.completed_at}",
    )


def _finish_post_maintenance_if_applicable(doc) -> None:
    if not doc.maintenance_ticket:
        return
    ticket = _lock("Hotel Maintenance Ticket", doc.maintenance_ticket)
    if ticket.status in ("Resolved", "Closed"):
        return
    if ticket.post_cleaning_task and ticket.post_cleaning_task != doc.name:
        return
    ticket.status = "Resolved"
    ticket.resolved_at = ticket.resolved_at or now_datetime()
    ticket.room_returned_at = now_datetime()
    _append_maintenance_log(ticket, "Resolved", f"Post-maintenance cleaning {doc.name} passed inspection.")
    ticket.save(ignore_permissions=True)
    if ticket.room:
        restore_room_after_engineering(ticket.room, source_name=ticket.name, housekeeping_status="Inspected")
    notify_roles(
        ["Engineering", "Engineering Supervisor", "Front Desk", "Hotel Manager"],
        property_name=ticket.property,
        subject=_("Maintenance completed and room {0} returned").format(ticket.room or ticket.location),
        message=_("Ticket {0} and post-maintenance cleaning {1} are complete.").format(ticket.name, doc.name),
        document_type=ticket.doctype,
        document_name=ticket.name,
        dedupe_key=f"maintenance-returned:{ticket.name}",
    )


@frappe.whitelist()
def report_lost_and_found(task: str, data, idempotency_key: str) -> dict:
    _require_any(HK_STAFF_ROLES)
    doc = _lock("Hotel Housekeeping Task", task)
    _can_operate_task(doc)
    payload = _parse(data)
    key = make_sync_key("LNF", task, idempotency_key)
    existing = frappe.db.get_value("Hotel Lost and Found", {"idempotency_key": key}, "name")
    if existing:
        return {"lost_and_found": existing, "already_processed": True}
    lost = frappe.get_doc(
        {
            "doctype": "Hotel Lost and Found",
            "property": doc.property,
            "room": doc.room,
            "reservation": doc.reservation,
            "housekeeping_task": doc.name,
            "status": "Found",
            "sensitive_item": cint(payload.get("sensitive_item")),
            "item_category": payload.get("item_category") or "Other",
            "item_description": payload.get("item_description"),
            "found_at": payload.get("found_at") or now_datetime(),
            "found_location": payload.get("found_location"),
            "found_by": frappe.session.user,
            "witnessed_by": payload.get("witnessed_by"),
            "item_photo": payload.get("item_photo"),
            "storage_location": payload.get("storage_location"),
            "bag_or_seal_number": payload.get("bag_or_seal_number"),
            "idempotency_key": key,
            "notes": payload.get("notes"),
        }
    ).insert(ignore_permissions=True)
    notify_roles(
        ["Housekeeping Supervisor", "Front Desk", "Hotel Manager"],
        property_name=doc.property,
        subject=_("Lost & Found reported in room {0}").format(doc.room),
        message=_("{0}: {1}").format(lost.item_category, lost.item_description),
        document_type=lost.doctype,
        document_name=lost.name,
        dedupe_key=f"lost-found:{lost.name}",
    )
    return {"lost_and_found": lost.name, "already_processed": False}


@frappe.whitelist()
def add_lost_found_custody(record: str, action: str, location: str | None = None, to_user: str | None = None, notes: str | None = None, handover_photo: str | None = None, idempotency_key: str | None = None) -> dict:
    _require_any(HK_SUPERVISOR_ROLES | FRONT_DESK_ROLES)
    doc = _lock("Hotel Lost and Found", record)
    key = make_sync_key("LNF-CUSTODY", record, idempotency_key) if idempotency_key else None
    if key and any(row.idempotency_key == key for row in doc.custody_logs):
        return {"lost_and_found": doc.name, "status": doc.status, "already_processed": True}
    status_map = {
        "Received by Supervisor": "Received by Supervisor",
        "Stored": "Stored",
        "Guest Contacted": "Guest Contacted",
        "Claimed": "Claimed",
        "Shipped": "Shipped",
        "Returned": "Returned",
        "Disposed": "Disposed",
    }
    doc.append(
        "custody_logs",
        {
            "event_at": now_datetime(),
            "action": action,
            "from_user": frappe.session.user,
            "to_user": to_user,
            "location": location,
            "notes": notes,
            "handover_photo": handover_photo,
            "idempotency_key": key,
        },
    )
    if action in status_map:
        doc.status = status_map[action]
    if location:
        doc.storage_location = location
    if action == "Guest Contacted":
        doc.guest_contacted_at = now_datetime()
        doc.guest_contact_notes = notes
    if action in ("Returned", "Shipped", "Claimed"):
        doc.returned_at = now_datetime()
        doc.returned_to = notes or to_user
    doc.save(ignore_permissions=True)
    return {"lost_and_found": doc.name, "status": doc.status, "already_processed": False}


@frappe.whitelist()
def report_maintenance_issue(data, idempotency_key: str) -> dict:
    _require_any(FRONT_DESK_ROLES | HK_STAFF_ROLES | ENGINEERING_ROLES)
    payload = _parse(data)
    key = make_sync_key("MAINT", payload.get("room") or payload.get("location") or "-", idempotency_key)
    existing = frappe.db.get_value("Hotel Maintenance Ticket", {"idempotency_key": key}, "name")
    if existing:
        return {"ticket": existing, "already_processed": True}
    source = payload.get("source") or ("Housekeeping" if _roles() & HK_STAFF_ROLES else "Front Office")
    ticket = frappe.get_doc(
        {
            "doctype": "Hotel Maintenance Ticket",
            "property": payload.get("property") or frappe.db.get_value("Hotel Room", payload.get("room"), "property"),
            "subject": payload.get("subject"),
            "status": "Open",
            "priority": payload.get("priority") or "Medium",
            "source": source,
            "problem_category": payload.get("problem_category") or "Other",
            "problem_code": payload.get("problem_code"),
            "room": payload.get("room"),
            "reservation": payload.get("reservation"),
            "originating_housekeeping_task": payload.get("housekeeping_task"),
            "location": payload.get("location"),
            "asset": payload.get("asset"),
            "description": payload.get("description"),
            "guest_impact": payload.get("guest_impact") or "None",
            "safety_risk": cint(payload.get("safety_risk")),
            "affects_room_sale": cint(payload.get("affects_room_sale")),
            "before_photo": payload.get("before_photo"),
            "idempotency_key": key,
        }
    ).insert(ignore_permissions=True)
    if payload.get("housekeeping_task") and payload.get("checklist_row"):
        hk = frappe.get_doc("Hotel Housekeeping Task", payload["housekeeping_task"])
        row = next((r for r in hk.checklist_items if r.name == payload["checklist_row"]), None)
        if row:
            row.result = "Reported to Engineering"
            row.maintenance_ticket = ticket.name
            hk.maintenance_ticket = ticket.name
            if hk.status == "In Progress":
                hk.status = "Waiting Engineering"
                hk.paused_at = now_datetime()
                hk.pause_reason = ticket.subject
                _append_hk_log(hk, "Paused", f"Waiting Engineering: {ticket.name}")
            hk.save(ignore_permissions=True)
    if ticket.room:
        set_room_status(
            ticket.room,
            operational_status="Out of Service" if ticket.affects_room_sale else None,
            housekeeping_status="Waiting Engineering" if payload.get("housekeeping_task") else None,
            event_type="Engineering Block" if ticket.affects_room_sale else "Engineering Issue Reported",
            source_doctype=ticket.doctype,
            source_name=ticket.name,
            notes=ticket.subject,
            idempotency_key=f"block:{ticket.name}",
        )
    notify_roles(
        ["Engineering", "Engineering Supervisor", "Hotel Manager"],
        property_name=ticket.property,
        subject=_("Engineering ticket {0}: {1}").format(ticket.name, ticket.subject),
        message=_("Priority: {0}; room/location: {1}").format(ticket.priority, ticket.room or ticket.location),
        document_type=ticket.doctype,
        document_name=ticket.name,
        dedupe_key=f"maintenance-new:{ticket.name}",
    )
    return {"ticket": ticket.name, "already_processed": False}


@frappe.whitelist()
def get_engineering_queue(property: str | None = None, include_closed: int = 0) -> dict:
    _require_any(ENGINEERING_ROLES | FRONT_DESK_ROLES | HK_SUPERVISOR_ROLES)
    filters = {"property": property} if property else {}
    if not cint(include_closed):
        filters["status"] = ("not in", ["Resolved", "Closed", "Cancelled"])
    conditions = ["1=1"]
    values = {}
    if property:
        conditions.append("property=%(property)s")
        values["property"] = property
    if not cint(include_closed):
        conditions.append("status not in ('Resolved','Closed','Cancelled')")
    rows = frappe.db.sql(
        f"""
        select name,property,subject,status,priority,source,room,location,assigned_to,reported_at,
               response_due_at,resolution_due_at,sla_status,guest_impact,affects_room_sale
        from `tabHotel Maintenance Ticket`
        where {' and '.join(conditions)}
        order by case when priority like 'Critical%%' then 1 when priority like 'High%%' then 2 when priority='Medium' then 3 else 4 end,
                 reported_at asc
        """,
        values,
        as_dict=True,
    )
    return {"tickets": rows, "server_time": now_datetime()}


@frappe.whitelist()
def acknowledge_maintenance(ticket: str) -> dict:
    _require_any(ENGINEERING_ROLES)
    doc = _lock("Hotel Maintenance Ticket", ticket)
    if doc.acknowledged_at:
        return {"ticket": doc.name, "already_processed": True}
    if doc.status not in ("Open", "Assigned"):
        frappe.throw(_("Ticket cannot be acknowledged in status {0}.").format(doc.status))
    doc.acknowledged_at = now_datetime()
    doc.status = "Acknowledged"
    _append_maintenance_log(doc, "Acknowledged")
    doc.save(ignore_permissions=True)
    return {"ticket": doc.name, "status": doc.status, "acknowledged_at": doc.acknowledged_at}


@frappe.whitelist()
def assign_maintenance(ticket: str, assigned_to: str) -> dict:
    _require_any(ENGINEERING_SUPERVISOR_ROLES)
    doc = _lock("Hotel Maintenance Ticket", ticket)
    if doc.status in ("Resolved", "Closed", "Cancelled"):
        frappe.throw(_("Closed tickets cannot be assigned."))
    if not frappe.db.get_value("User", assigned_to, "enabled"):
        frappe.throw(_("Assigned user is disabled or missing."))
    if not (set(frappe.get_roles(assigned_to)) & ENGINEERING_ROLES):
        frappe.throw(_("Assigned user does not have an Engineering role."))
    doc.assigned_to = assigned_to
    doc.status = "Assigned"
    _append_maintenance_log(doc, "Assigned", f"Assigned to {assigned_to}")
    doc.save(ignore_permissions=True)
    notify_users(
        [assigned_to],
        subject=_("Engineering ticket assigned: {0}").format(doc.subject),
        message=_("Ticket {0}, priority {1}, room/location {2}").format(doc.name, doc.priority, doc.room or doc.location),
        document_type=doc.doctype,
        document_name=doc.name,
        dedupe_key=f"maintenance-assigned:{doc.name}:{assigned_to}",
    )
    return {"ticket": doc.name, "assigned_to": assigned_to}


def _can_operate_ticket(doc) -> None:
    _require_any(ENGINEERING_ROLES)
    if doc.assigned_to and doc.assigned_to != frappe.session.user and not (_roles() & ENGINEERING_SUPERVISOR_ROLES):
        frappe.throw(_("Ticket is assigned to {0}.").format(doc.assigned_to))


@frappe.whitelist()
def start_maintenance(ticket: str) -> dict:
    doc = _lock("Hotel Maintenance Ticket", ticket)
    _can_operate_ticket(doc)
    if doc.status == "In Progress":
        return {"ticket": doc.name, "already_processed": True}
    if doc.status not in ("Open", "Acknowledged", "Assigned", "Paused", "Waiting Parts", "Waiting Vendor"):
        frappe.throw(_("Ticket cannot be started in status {0}.").format(doc.status))
    doc.acknowledged_at = doc.acknowledged_at or now_datetime()
    doc.started_at = doc.started_at or now_datetime()
    doc.assigned_to = doc.assigned_to or frappe.session.user
    doc.status = "In Progress"
    doc.waiting_reason = None
    _append_maintenance_log(doc, "Started")
    doc.save(ignore_permissions=True)
    return {"ticket": doc.name, "status": doc.status, "started_at": doc.started_at}


@frappe.whitelist()
def pause_maintenance(ticket: str, reason: str, waiting_status: str = "Paused") -> dict:
    doc = _lock("Hotel Maintenance Ticket", ticket)
    _can_operate_ticket(doc)
    if waiting_status not in ("Paused", "Waiting Vendor", "Waiting Parts"):
        frappe.throw(_("Invalid waiting status."))
    if doc.status != "In Progress":
        frappe.throw(_("Only an in-progress ticket can be paused."))
    doc.status = waiting_status
    doc.waiting_reason = reason
    _append_maintenance_log(doc, "Waiting Vendor" if waiting_status == "Waiting Vendor" else "Waiting Parts" if waiting_status == "Waiting Parts" else "Paused", reason)
    doc.save(ignore_permissions=True)
    return {"ticket": doc.name, "status": doc.status}


@frappe.whitelist()
def complete_maintenance(ticket: str, data, idempotency_key: str) -> dict:
    doc = _lock("Hotel Maintenance Ticket", ticket)
    _can_operate_ticket(doc)
    if doc.status in ("Post-Maintenance Cleaning", "Resolved", "Closed"):
        return {"ticket": doc.name, "post_cleaning_task": doc.post_cleaning_task, "already_processed": True}
    if doc.status not in ("In Progress", "Paused", "Waiting Vendor", "Waiting Parts", "Assigned", "Acknowledged"):
        frappe.throw(_("Ticket cannot be completed in status {0}.").format(doc.status))
    payload = _parse(data)
    if not payload.get("root_cause") or not payload.get("corrective_action"):
        frappe.throw(_("Root cause and corrective action are required before completing repair."))
    doc.root_cause = payload.get("root_cause")
    doc.corrective_action = payload.get("corrective_action")
    doc.materials_used = payload.get("materials_used")
    doc.prevention_notes = payload.get("prevention_notes")
    doc.post_maintenance_cleaning_required = cint(payload.get("post_maintenance_cleaning_required"))
    doc.cleaning_instructions = payload.get("cleaning_instructions")
    doc.after_photo = payload.get("after_photo") or doc.after_photo
    doc.status = "Repair Completed"
    _append_maintenance_log(doc, "Repair Completed", doc.corrective_action, doc.materials_used)
    doc.save(ignore_permissions=True)
    cleaning_task = None
    if doc.post_maintenance_cleaning_required:
        if not doc.room:
            frappe.throw(_("A room is required for post-maintenance housekeeping. Use a manual cleaning task for non-room locations."))
        if not doc.cleaning_instructions:
            frappe.throw(_("Practical cleaning instructions are required when post-maintenance cleaning is requested."))
        origin_task = None
        if doc.originating_housekeeping_task and frappe.db.exists("Hotel Housekeeping Task", doc.originating_housekeeping_task):
            origin_task = _lock("Hotel Housekeeping Task", doc.originating_housekeeping_task)
        if origin_task and origin_task.status not in ("Completed", "Cancelled"):
            for checklist_row in origin_task.checklist_items:
                if checklist_row.maintenance_ticket == doc.name and checklist_row.result == "Reported to Engineering":
                    checklist_row.result = "Pending"
                    checklist_row.notes = "Repair completed; verify the item before completing cleaning."
            if origin_task.paused_at:
                origin_task.total_pause_minutes = flt(origin_task.total_pause_minutes) + max(
                    (now_datetime() - get_datetime(origin_task.paused_at)).total_seconds() / 60, 0
                )
            origin_task.status = "Assigned"
            origin_task.paused_at = None
            origin_task.pause_reason = None
            origin_task.maintenance_ticket = doc.name
            origin_task.notes = "\n".join(filter(None, [origin_task.notes, doc.cleaning_instructions]))
            _append_hk_log(origin_task, "Resumed", f"Engineering repair {doc.name} completed; cleaning may continue.")
            origin_task.save(ignore_permissions=True)
            cleaning_task = origin_task.name
        else:
            from hotel_pms.tasks import ensure_housekeeping_task
            cleaning_task, _ = ensure_housekeeping_task(
                property_name=doc.property,
                room=doc.room,
                task_date=getdate(),
                task_type="Post-Maintenance Cleaning",
                reservation=doc.reservation,
                maintenance_ticket=doc.name,
                source="Engineering",
            )
        doc.post_cleaning_task = cleaning_task
        doc.status = "Post-Maintenance Cleaning"
        _append_maintenance_log(doc, "Cleaning Requested", doc.cleaning_instructions)
        doc.save(ignore_permissions=True)
        if doc.room:
            set_room_status(
                doc.room,
                operational_status="Out of Service" if doc.affects_room_sale else None,
                housekeeping_status="Post-Maintenance Cleaning",
                event_type="Post-Maintenance Cleaning Requested",
                source_doctype=doc.doctype,
                source_name=doc.name,
                notes=doc.cleaning_instructions,
                idempotency_key=f"post-cleaning:{doc.name}",
            )
        notify_roles(
            ["Housekeeping", "Housekeeping Supervisor", "Hotel Manager"],
            property_name=doc.property,
            subject=_("Post-maintenance cleaning required: {0}").format(doc.room or doc.location),
            message=doc.cleaning_instructions,
            document_type="Hotel Housekeeping Task",
            document_name=cleaning_task,
            dedupe_key=f"post-cleaning-task:{cleaning_task}",
        )
    else:
        doc.status = "Resolved"
        doc.resolved_at = now_datetime()
        doc.room_returned_at = now_datetime()
        _append_maintenance_log(doc, "Resolved", "Repair completed without post-maintenance cleaning.")
        doc.save(ignore_permissions=True)
        origin_task = frappe.get_doc("Hotel Housekeeping Task", doc.originating_housekeeping_task) if doc.originating_housekeeping_task and frappe.db.exists("Hotel Housekeeping Task", doc.originating_housekeeping_task) else None
        if origin_task and origin_task.status == "Waiting Engineering":
            for checklist_row in origin_task.checklist_items:
                if checklist_row.maintenance_ticket == doc.name and checklist_row.result == "Reported to Engineering":
                    checklist_row.result = "Pending"
                    checklist_row.notes = "Repair completed; verify the item before completing cleaning."
            if origin_task.paused_at:
                origin_task.total_pause_minutes = flt(origin_task.total_pause_minutes) + max((now_datetime() - get_datetime(origin_task.paused_at)).total_seconds() / 60, 0)
            origin_task.status = "Assigned"
            origin_task.paused_at = None
            origin_task.pause_reason = None
            _append_hk_log(origin_task, "Resumed", f"Engineering ticket {doc.name} resolved; continue cleaning.")
            origin_task.save(ignore_permissions=True)
            if doc.room:
                set_room_status(
                    doc.room,
                    operational_status=expected_operational_status(doc.room),
                    housekeeping_status="Assigned",
                    event_type="Engineering Repair Completed - Cleaning Resume",
                    source_doctype=doc.doctype,
                    source_name=doc.name,
                    idempotency_key=f"repair-resume:{doc.name}",
                )
            if origin_task.assigned_to:
                notify_users([origin_task.assigned_to], subject=_("Engineering completed in room {0}").format(doc.room), message=_("Resume housekeeping task {0}.").format(origin_task.name), document_type=origin_task.doctype, document_name=origin_task.name, dedupe_key=f"repair-resume-notify:{doc.name}")
        elif doc.room and doc.affects_room_sale:
            restore_room_after_engineering(doc.room, source_name=doc.name, housekeeping_status="Inspected")
        notify_roles(
            ["Front Desk", "Housekeeping Supervisor", "Hotel Manager"],
            property_name=doc.property,
            subject=_("Engineering ticket resolved: {0}").format(doc.subject),
            message=_("Ticket {0} is resolved. Room/location: {1}").format(doc.name, doc.room or doc.location),
            document_type=doc.doctype,
            document_name=doc.name,
            dedupe_key=f"maintenance-resolved:{doc.name}",
        )
    _auto_create_sop_candidate_if_needed(doc)
    return {"ticket": doc.name, "status": doc.status, "post_cleaning_task": cleaning_task, "already_processed": False}


@frappe.whitelist()
def close_maintenance(ticket: str, notes: str | None = None) -> dict:
    _require_any(ENGINEERING_SUPERVISOR_ROLES)
    doc = _lock("Hotel Maintenance Ticket", ticket)
    if doc.status == "Closed":
        return {"ticket": doc.name, "already_processed": True}
    if doc.status != "Resolved":
        frappe.throw(_("Only a resolved ticket can be closed."))
    doc.status = "Closed"
    doc.closed_at = now_datetime()
    _append_maintenance_log(doc, "Closed", notes)
    doc.save(ignore_permissions=True)
    return {"ticket": doc.name, "status": doc.status}


def _repeat_problem_count(doc) -> int:
    filters = {"property": doc.property, "name": ("!=", doc.name), "status": ("not in", ["Cancelled"])}
    if doc.problem_code:
        filters["problem_code"] = doc.problem_code
    else:
        filters["problem_category"] = doc.problem_category
        if doc.room:
            filters["room"] = doc.room
    return frappe.db.count("Hotel Maintenance Ticket", filters) + 1


def _auto_create_sop_candidate_if_needed(doc) -> str | None:
    settings = frappe.get_single("Hotel PMS Settings")
    if not cint(settings.auto_create_sop_candidate):
        return None
    repeat_count = _repeat_problem_count(doc)
    has_learning = bool(doc.prevention_notes or doc.cleaning_instructions)
    if should_create_sop_candidate(repeat_count=repeat_count, threshold=settings.sop_repeat_threshold or 3, has_learning=has_learning):
        return _create_sop_candidate(doc, repeat_count, make_sync_key("SOP", doc.name))
    return None


def _create_sop_candidate(doc, repeat_count: int, key: str) -> str:
    existing = frappe.db.get_value("Hotel SOP Candidate", {"source_ticket": doc.name}, "name")
    if existing:
        return existing
    candidate = frappe.get_doc(
        {
            "doctype": "Hotel SOP Candidate",
            "title": f"{doc.problem_category}: {doc.subject}",
            "property": doc.property,
            "source_ticket": doc.name,
            "room": doc.room,
            "problem_category": doc.problem_category,
            "problem_code": doc.problem_code,
            "status": "Draft Candidate",
            "repeat_count": repeat_count,
            "idempotency_key": key,
            "symptoms": doc.description,
            "root_cause": doc.root_cause,
            "repair_steps": doc.corrective_action,
            "cleaning_steps": doc.cleaning_instructions,
            "materials_and_tools": doc.materials_used,
            "prevention": doc.prevention_notes,
            "before_photo": doc.before_photo,
            "after_photo": doc.after_photo,
        }
    ).insert(ignore_permissions=True)
    doc.db_set("sop_candidate", candidate.name)
    return candidate.name


@frappe.whitelist()
def create_sop_candidate(ticket: str) -> dict:
    _require_any(ENGINEERING_SUPERVISOR_ROLES | HK_SUPERVISOR_ROLES)
    doc = _lock("Hotel Maintenance Ticket", ticket)
    if doc.status not in ("Repair Completed", "Post-Maintenance Cleaning", "Resolved", "Closed"):
        frappe.throw(_("Complete the repair before creating an SOP candidate."))
    candidate = _create_sop_candidate(doc, _repeat_problem_count(doc), make_sync_key("SOP", doc.name))
    return {"ticket": doc.name, "sop_candidate": candidate}


@frappe.whitelist()
def get_room_history(room: str, limit: int = 200) -> dict:
    _require_any(FRONT_DESK_ROLES | HK_STAFF_ROLES | ENGINEERING_ROLES)
    room_doc = frappe.get_doc("Hotel Room", room)
    room_doc.check_permission("read")
    timeline = []
    for row in frappe.get_all(
        "Hotel Room Status Log",
        filters={"room": room},
        fields=["name","event_at","event_type","old_operational_status","new_operational_status","old_housekeeping_status","new_housekeeping_status","source_doctype","source_name","changed_by","notes"],
        order_by="event_at desc",
        limit=limit,
    ):
        timeline.append({"timestamp": row.event_at, "type": "Room Status", "title": row.event_type, "detail": row.notes, "reference_doctype": row.source_doctype, "reference_name": row.source_name, **row})
    for row in frappe.get_all(
        "Hotel Maintenance Ticket",
        filters={"room": room},
        fields=["name","reported_at","subject","status","priority","source","root_cause","corrective_action","prevention_notes"],
        order_by="reported_at desc",
        limit=limit,
    ):
        timeline.append({"timestamp": row.reported_at, "type": "Maintenance", "title": row.subject, "detail": f"{row.status} · {row.priority}", "reference_doctype": "Hotel Maintenance Ticket", "reference_name": row.name, **row})
    for row in frappe.get_all(
        "Hotel Housekeeping Task",
        filters={"room": room},
        fields=["name","creation","task_type","status","assigned_to","started_at","completed_at","inspected_at","cleaning_minutes","first_pass"],
        order_by="creation desc",
        limit=limit,
    ):
        timeline.append({"timestamp": row.creation, "type": "Housekeeping", "title": row.task_type, "detail": f"{row.status} · {row.cleaning_minutes or 0} min", "reference_doctype": "Hotel Housekeeping Task", "reference_name": row.name, **row})
    for row in frappe.get_all(
        "Hotel Lost and Found",
        filters={"room": room},
        fields=["name","found_at","item_category","item_description","status","found_by"],
        order_by="found_at desc",
        limit=limit,
    ):
        timeline.append({"timestamp": row.found_at, "type": "Lost & Found", "title": row.item_description, "detail": f"{row.item_category} · {row.status}", "reference_doctype": "Hotel Lost and Found", "reference_name": row.name, **row})
    timeline.sort(key=lambda x: get_datetime(x["timestamp"]) if x.get("timestamp") else datetime.min, reverse=True)
    return {"room": room_doc.as_dict(), "timeline": timeline[: int(limit)]}


@frappe.whitelist()
def get_operations_dashboard(property: str | None = None) -> dict:
    _require_any(FRONT_DESK_ROLES | HK_STAFF_ROLES | ENGINEERING_ROLES)
    property = property or frappe.db.get_single_value("Hotel PMS Settings", "default_property")
    filters = {"property": property} if property else {}
    hk = frappe.get_all("Hotel Housekeeping Task", filters={**filters, "task_date": ("<=", getdate()), "status": ("not in", ["Completed", "Cancelled"])}, fields=["status", "priority"])
    maint = frappe.get_all("Hotel Maintenance Ticket", filters={**filters, "status": ("not in", ["Resolved", "Closed", "Cancelled"])}, fields=["status", "priority", "sla_status", "affects_room_sale"])
    return {
        "property": property,
        "housekeeping": {"total": len(hk), "critical": sum(1 for r in hk if r.priority == "Critical"), "inspection": sum(1 for r in hk if r.status == "Ready for Inspection"), "reclean": sum(1 for r in hk if r.status == "Reclean Required")},
        "engineering": {"total": len(maint), "critical": sum(1 for r in maint if str(r.priority).startswith("Critical")), "sla_breached": sum(1 for r in maint if "Breached" in (r.sla_status or "")), "rooms_blocked": sum(1 for r in maint if r.affects_room_sale)},
        "lost_found_open": frappe.db.count("Hotel Lost and Found", {**filters, "status": ("not in", ["Returned", "Disposed", "Claimed"])}),
        "server_time": now_datetime(),
    }


def monitor_operation_slas() -> None:
    tickets = frappe.get_all(
        "Hotel Maintenance Ticket",
        filters={"status": ("not in", ["Resolved", "Closed", "Cancelled"])},
        fields=["name","property","subject","status","priority","response_due_at","resolution_due_at","acknowledged_at","resolved_at","sla_status","response_breach_notified","resolution_breach_notified"],
    )
    now = now_datetime()
    for row in tickets:
        new_status = calculate_sla_status(
            now=now,
            response_due_at=get_datetime(row.response_due_at) if row.response_due_at else None,
            resolution_due_at=get_datetime(row.resolution_due_at) if row.resolution_due_at else None,
            acknowledged_at=get_datetime(row.acknowledged_at) if row.acknowledged_at else None,
            resolved_at=get_datetime(row.resolved_at) if row.resolved_at else None,
        )
        updates = {}
        if new_status != row.sla_status:
            updates["sla_status"] = new_status
        notify = False
        if new_status == "Response Breached" and not row.response_breach_notified:
            updates["response_breach_notified"] = 1
            notify = True
        if new_status == "Resolution Breached" and not row.resolution_breach_notified:
            updates["resolution_breach_notified"] = 1
            notify = True
        if updates:
            frappe.db.set_value("Hotel Maintenance Ticket", row.name, updates, update_modified=False)
        if notify:
            notify_roles(
                ["Engineering Supervisor", "Hotel Manager"],
                property_name=row.property,
                subject=_("Maintenance SLA breached: {0}").format(row.subject),
                message=_("Ticket {0} is now {1}.").format(row.name, new_status),
                document_type="Hotel Maintenance Ticket",
                document_name=row.name,
                dedupe_key=f"sla:{row.name}:{new_status}",
            )
