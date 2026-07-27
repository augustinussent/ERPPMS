from __future__ import annotations

from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, getdate, now_datetime

from hotel_pms.media import validate_photo_fields
from hotel_pms.operations_rules import elapsed_minutes, housekeeping_priority_score


class HotelHousekeepingTask(Document):
    def before_insert(self):
        self.task_date = self.task_date or getdate()
        self._set_next_arrival_and_priority()
        self._populate_checklist()

    def validate(self):
        validate_photo_fields(self, {"before_photo", "after_photo"})
        self._set_next_arrival_and_priority()
        if self.assigned_to and not self.assigned_at:
            self.assigned_at = now_datetime()
            if self.status == "Open":
                self.status = "Assigned"
        if self.completed_at and self.started_at:
            self.cleaning_minutes = elapsed_minutes(
                get_datetime(self.started_at), get_datetime(self.completed_at), self.total_pause_minutes or 0
            )
        if self.requires_photo_evidence() and not self.after_photo:
            # Do not make photo evidence mandatory when uploads are globally disabled.
            from hotel_pms.media import photo_uploads_enabled
            if photo_uploads_enabled() and self.status in ("Ready for Inspection", "Completed"):
                frappe.throw(_("After Photo is required by a critical checklist item."))

    def requires_photo_evidence(self) -> bool:
        return any(row.requires_photo and row.result == "OK" for row in self.checklist_items)

    def _set_next_arrival_and_priority(self):
        if not self.room:
            return
        next_rows = frappe.db.sql(
            """
            select r.name, r.arrival_date, p.check_in_time
            from `tabHotel Reservation` r
            inner join `tabHotel Reservation Room` rr on rr.parent=r.name
            inner join `tabHotel Property` p on p.name=r.property
            where rr.room=%(room)s
              and r.docstatus < 2
              and r.status in ('Tentative','Confirmed')
              and r.arrival_date >= %(task_date)s
              and (%(reservation)s='' or r.name != %(reservation)s)
            order by r.arrival_date asc
            limit 1
            """,
            {"room": self.room, "task_date": self.task_date, "reservation": self.reservation or ""},
            as_dict=True,
        )
        minutes_to_arrival = None
        if next_rows:
            row = next_rows[0]
            self.next_arrival_at = get_datetime(f"{row.arrival_date} {row.check_in_time or '14:00:00'}")
            minutes_to_arrival = int((get_datetime(self.next_arrival_at) - now_datetime()).total_seconds() / 60)
            if not self.target_ready_at:
                self.target_ready_at = self.next_arrival_at
        score = housekeeping_priority_score(
            guest_waiting=bool(self.guest_waiting),
            minutes_to_next_arrival=minutes_to_arrival,
            task_type=self.task_type,
        )
        self.priority_score = score
        self.priority = "Critical" if score >= 900 else "High" if score >= 450 else "Normal" if score >= 150 else "Low"

    def _populate_checklist(self):
        if self.checklist_items or not self.property or not self.task_type:
            return
        room_type = frappe.db.get_value("Hotel Room", self.room, "room_type") if self.room else None
        template = None
        if room_type:
            template = frappe.db.get_value(
                "Hotel Cleaning Checklist Template",
                {"property": self.property, "room_type": room_type, "task_type": self.task_type, "enabled": 1},
                "name",
                order_by="modified desc",
            )
        if not template:
            template = frappe.db.get_value(
                "Hotel Cleaning Checklist Template",
                {"property": self.property, "room_type": ("is", "not set"), "task_type": self.task_type, "enabled": 1},
                "name",
                order_by="modified desc",
            )
        if not template:
            return
        template_doc = frappe.get_doc("Hotel Cleaning Checklist Template", template)
        self.checklist_template = template_doc.name
        for row in template_doc.items:
            self.append(
                "checklist_items",
                {
                    "template_item": row.name,
                    "sequence": row.sequence,
                    "area": row.area,
                    "item_label": row.item_label,
                    "result": "Pending",
                    "is_critical": row.is_critical,
                    "weight": row.weight or 1,
                    "requires_photo": row.requires_photo,
                    "notes": row.instructions,
                },
            )
