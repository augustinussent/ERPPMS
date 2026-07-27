from __future__ import annotations

import frappe
from frappe.utils import now_datetime

from hotel_pms.sync import make_sync_key


def expected_operational_status(room: str) -> str:
    occupied = frappe.db.sql(
        """
        select 1
        from `tabHotel Reservation` r
        inner join `tabHotel Reservation Room` rr on rr.parent = r.name
        where rr.room=%s and r.docstatus=1 and r.status='Checked In'
        limit 1
        """,
        room,
    )
    return "Occupied" if occupied else "Available"


def set_room_status(
    room: str,
    *,
    operational_status: str | None = None,
    housekeeping_status: str | None = None,
    event_type: str,
    source_doctype: str | None = None,
    source_name: str | None = None,
    notes: str | None = None,
    idempotency_key: str | None = None,
) -> bool:
    rows = frappe.db.sql(
        "select name, property, operational_status, housekeeping_status from `tabHotel Room` where name=%s for update",
        room,
        as_dict=True,
    )
    if not rows:
        frappe.throw(f"Hotel Room {room} does not exist")
    current = rows[0]
    new_operational = operational_status or current.operational_status
    new_housekeeping = housekeeping_status or current.housekeeping_status
    if new_operational == current.operational_status and new_housekeeping == current.housekeeping_status:
        return False
    frappe.db.set_value(
        "Hotel Room",
        room,
        {"operational_status": new_operational, "housekeeping_status": new_housekeeping},
        update_modified=False,
    )
    log_key = make_sync_key("ROOMSTATUS", room, idempotency_key) if idempotency_key else None
    if log_key and frappe.db.exists("Hotel Room Status Log", {"idempotency_key": log_key}):
        return True
    log = frappe.get_doc(
        {
            "doctype": "Hotel Room Status Log",
            "property": current.property,
            "room": room,
            "event_at": now_datetime(),
            "event_type": event_type,
            "old_operational_status": current.operational_status,
            "new_operational_status": new_operational,
            "old_housekeeping_status": current.housekeeping_status,
            "new_housekeeping_status": new_housekeeping,
            "source_doctype": source_doctype,
            "source_name": source_name,
            "changed_by": frappe.session.user if frappe.session.user != "Guest" else "Administrator",
            "notes": notes,
            "idempotency_key": log_key,
        }
    )
    log.insert(ignore_permissions=True)
    frappe.publish_realtime(
        "hotel_room_status_changed",
        {"room": room, "operational_status": new_operational, "housekeeping_status": new_housekeeping, "event_type": event_type},
        after_commit=True,
    )
    return True


def restore_room_after_engineering(room: str, *, source_name: str, housekeeping_status: str = "Inspected") -> None:
    set_room_status(
        room,
        operational_status=expected_operational_status(room),
        housekeeping_status=housekeeping_status,
        event_type="Returned to Service",
        source_doctype="Hotel Maintenance Ticket",
        source_name=source_name,
        idempotency_key=f"restore:{source_name}:{housekeeping_status}",
    )
