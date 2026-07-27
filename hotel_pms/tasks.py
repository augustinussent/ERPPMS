from __future__ import annotations

import frappe
from frappe.utils import add_days, getdate


def create_housekeeping_tasks() -> None:
    today = getdate()
    rooms = frappe.get_all(
        "Hotel Room",
        filters={"enabled": 1, "operational_status": ("not in", ["Out of Order", "Out of Service"])},
        fields=["name", "property", "housekeeping_status"],
    )
    for room in rooms:
        if room.housekeeping_status not in ("Dirty", "Pickup"):
            continue
        if frappe.db.exists("Hotel Housekeeping Task", {"room": room.name, "task_date": today, "status": ("!=", "Cancelled")}):
            continue
        frappe.get_doc(
            {
                "doctype": "Hotel Housekeeping Task",
                "property": room.property,
                "room": room.name,
                "task_date": today,
                "task_type": "Checkout Clean" if room.housekeeping_status == "Dirty" else "Pickup",
                "status": "Open",
            }
        ).insert(ignore_permissions=True)


def create_preventive_maintenance_tasks() -> None:
    """Create tasks from active maintenance schedules due today.

    The schedule doctype is intentionally generic so hotel SOP intervals can be
    represented without hard-coding every pump, filter, gutter, or genset into Python.
    """
    today = getdate()
    schedules = frappe.get_all(
        "Hotel Preventive Maintenance Schedule",
        filters={"enabled": 1, "trigger_type": "Calendar", "next_due_date": ("<=", today)},
        fields=["name", "property", "asset", "location", "task_title", "priority", "interval_days", "next_due_date"],
    )
    for schedule in schedules:
        if not frappe.db.exists("Hotel Maintenance Ticket", {"preventive_schedule": schedule.name, "due_date": today}):
            frappe.get_doc(
                {
                    "doctype": "Hotel Maintenance Ticket",
                    "property": schedule.property,
                    "subject": schedule.task_title,
                    "description": schedule.task_title,
                    "source": "Preventive Maintenance",
                    "asset": schedule.asset,
                    "location": schedule.location,
                    "priority": schedule.priority or "Medium",
                    "status": "Open",
                    "due_date": today,
                    "preventive_schedule": schedule.name,
                    "is_preventive": 1,
                }
            ).insert(ignore_permissions=True)

        interval = schedule.interval_days or 30
        frappe.db.set_value(
            "Hotel Preventive Maintenance Schedule",
            schedule.name,
            "next_due_date",
            add_days(today, interval),
            update_modified=False,
        )
