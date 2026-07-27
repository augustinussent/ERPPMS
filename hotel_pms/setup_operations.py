from __future__ import annotations

import frappe


ROLES = ["Housekeeping Supervisor", "Engineering Supervisor"]


def setup_operations() -> None:
    for role_name in ROLES:
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert(ignore_permissions=True)
    _add_indexes()
    _backfill_room_status_log()


def _add_indexes() -> None:
    indexes = {
        "Hotel Housekeeping Task": [["property", "task_date", "status"], ["assigned_to", "status"], ["room", "status"]],
        "Hotel Maintenance Ticket": [["property", "status", "priority"], ["room", "status"], ["sla_status", "status"]],
        "Hotel Room Status Log": [["room", "event_at"]],
        "Hotel Lost and Found": [["property", "status"], ["room", "found_at"]],
    }
    for doctype, fields_list in indexes.items():
        if not frappe.db.exists("DocType", doctype):
            continue
        for fields in fields_list:
            try:
                frappe.db.add_index(doctype, fields)
            except Exception:
                # Index may already exist or the target database may choose an equivalent name.
                pass


def _backfill_room_status_log() -> None:
    if not frappe.db.exists("DocType", "Hotel Room Status Log"):
        return
    rooms = frappe.get_all("Hotel Room", fields=["name", "property", "operational_status", "housekeeping_status"])
    for room in rooms:
        if frappe.db.exists("Hotel Room Status Log", {"room": room.name}):
            continue
        frappe.get_doc(
            {
                "doctype": "Hotel Room Status Log",
                "property": room.property,
                "room": room.name,
                "event_at": frappe.utils.now_datetime(),
                "event_type": "v0.5 Baseline",
                "new_operational_status": room.operational_status,
                "new_housekeeping_status": room.housekeeping_status,
                "changed_by": "Administrator",
                "notes": "Baseline captured during Hotel PMS v0.5 operations migration.",
                "idempotency_key": f"ROOMSTATUS:BASELINE:{room.name}",
            }
        ).insert(ignore_permissions=True)
