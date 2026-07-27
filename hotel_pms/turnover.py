from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_datetime, getdate, nowdate

from hotel_pms.distribution_rules import turnover_window_minutes
from hotel_pms.platform import require_property
from hotel_pms.tasks import ensure_housekeeping_task


def _dt(day, time_value):
    value = str(time_value or "00:00:00")
    return get_datetime(f"{getdate(day)} {value}")


def turnover_plan(property_name: str, start_date=None, days: int = 14) -> list[dict]:
    require_property(property_name)
    start = getdate(start_date or nowdate())
    end = getdate(add_days(start, max(cint(days), 1)))
    prop = frappe.db.get_value("Hotel Property", property_name, ["check_in_time", "check_out_time"], as_dict=True) or {}
    rows = frappe.db.sql(
        """
        select r.name reservation, r.departure_date, rr.room, hr.room_number, hr.room_type, hr.floor
        from `tabHotel Reservation` r
        inner join `tabHotel Reservation Room` rr on rr.parent=r.name
        inner join `tabHotel Room` hr on hr.name=rr.room
        where r.property=%(property)s and r.docstatus < 2
          and r.status in ('Confirmed','Checked In')
          and r.departure_date >= %(start)s and r.departure_date < %(end)s
        order by r.departure_date asc, hr.room_number asc
        """,
        {"property": property_name, "start": start, "end": end}, as_dict=True,
    )
    output = []
    for row in rows:
        next_stay = frappe.db.sql(
            """
            select r.name, r.arrival_date, r.arrival_time, c.customer_name guest
            from `tabHotel Reservation` r
            inner join `tabHotel Reservation Room` rr on rr.parent=r.name
            left join `tabCustomer` c on c.name=r.guest
            where rr.room=%(room)s and r.docstatus < 2 and r.status in ('Tentative','Confirmed')
              and r.arrival_date >= %(departure)s and r.name != %(reservation)s
            order by r.arrival_date asc, r.arrival_time asc limit 1
            """,
            {"room": row.room, "departure": row.departure_date, "reservation": row.reservation}, as_dict=True,
        )
        next_row = next_stay[0] if next_stay else None
        same_day = bool(next_row and getdate(next_row.arrival_date) == getdate(row.departure_date))
        checkout_time = str(prop.get("check_out_time") or "12:00:00")
        checkin_time = str((next_row or {}).get("arrival_time") or prop.get("check_in_time") or "14:00:00")
        available_minutes = turnover_window_minutes(checkout_time[:5], checkin_time[:5]) if same_day else None
        task = frappe.db.get_value(
            "Hotel Housekeeping Task",
            {"room": row.room, "task_date": row.departure_date, "task_type": "Checkout Clean", "status": ("!=", "Cancelled")},
            ["name", "status", "assigned_to", "target_ready_at", "priority"], as_dict=True,
        )
        output.append({
            **row,
            "next_reservation": (next_row or {}).get("name"),
            "next_arrival_date": str((next_row or {}).get("arrival_date") or ""),
            "next_guest": (next_row or {}).get("guest") or "",
            "same_day_turnover": same_day,
            "available_minutes": available_minutes,
            "risk": "Critical" if same_day and available_minutes is not None and available_minutes < 120 else ("High" if same_day else "Normal"),
            "task": task,
        })
    return output


@frappe.whitelist()
def get_turnover_plan(property: str, start_date=None, days: int = 14) -> dict:
    frappe.only_for(["System Manager", "Hotel Manager", "Front Desk", "Housekeeping", "Housekeeping Supervisor"])
    rows = turnover_plan(property, start_date, days)
    conflicts = cleaner_conflicts(rows)
    return {"rows": rows, "cleaner_conflicts": conflicts}


def cleaner_conflicts(rows: list[dict]) -> list[dict]:
    by_user_date = defaultdict(list)
    for row in rows:
        task = row.get("task") or {}
        user = task.get("assigned_to") if isinstance(task, dict) else getattr(task, "assigned_to", None)
        if user:
            by_user_date[(user, str(row["departure_date"]))].append(row)
    output = []
    for (user, day), tasks in by_user_date.items():
        if len(tasks) > 1:
            output.append({
                "assigned_to": user,
                "date": day,
                "rooms": [row["room_number"] for row in tasks],
                "classification": "Cleaner Conflict",
                "backup_required": True,
            })
    return output


@frappe.whitelist()
def create_turnover_tasks(property: str | None = None, start_date=None, days: int = 14) -> dict:
    if frappe.session.user != "Administrator":
        frappe.only_for(["System Manager", "Hotel Manager", "Housekeeping Supervisor"])
    properties = [property] if property else frappe.get_all("Hotel Property", filters={"enabled": 1}, pluck="name")
    created = existing = 0
    for property_name in properties:
        for row in turnover_plan(property_name, start_date, days):
            name, already = ensure_housekeeping_task(
                property_name=property_name,
                room=row["room"],
                task_date=row["departure_date"],
                task_type="Checkout Clean",
                reservation=row["reservation"],
                source="Checkout",
            )
            existing += int(already); created += int(not already)
            updates = {}
            if row.get("next_reservation"):
                next_res = frappe.db.get_value("Hotel Reservation", row["next_reservation"], ["arrival_date", "arrival_time"], as_dict=True)
                prop = frappe.db.get_value("Hotel Property", property_name, "check_in_time")
                target = _dt(next_res.arrival_date, next_res.arrival_time or prop or "14:00:00")
                updates.update({"next_arrival_at": target, "target_ready_at": target - timedelta(minutes=30)})
            if row["risk"] == "Critical":
                updates.update({"priority": "Critical", "guest_waiting": 1})
            elif row["risk"] == "High":
                updates.update({"priority": "High"})
            if updates:
                frappe.db.set_value("Hotel Housekeeping Task", name, updates, update_modified=False)
    return {"created": created, "existing": existing}
