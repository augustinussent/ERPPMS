from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, now_datetime

from hotel_pms.media import validate_photo_fields
from hotel_pms.operations_rules import calculate_sla_status, get_sla_minutes


class HotelMaintenanceTicket(Document):
    def before_insert(self):
        self.reported_at = self.reported_at or now_datetime()
        self.reported_by = self.reported_by or frappe.session.user
        self._set_sla_deadlines()
        if not self.work_logs:
            self.append(
                "work_logs",
                {"event_at": self.reported_at, "action": "Reported", "user": self.reported_by, "notes": self.description},
            )

    def _set_sla_deadlines(self):
        settings = frappe.get_single("Hotel PMS Settings")
        response, resolution = get_sla_minutes(
            self.priority,
            {
                "critical_response_minutes": settings.critical_response_minutes,
                "critical_resolution_minutes": settings.critical_resolution_minutes,
                "high_response_minutes": settings.high_response_minutes,
                "high_resolution_minutes": settings.high_resolution_minutes,
                "medium_response_minutes": settings.medium_response_minutes,
                "medium_resolution_minutes": settings.medium_resolution_minutes,
                "low_response_minutes": settings.low_response_minutes,
                "low_resolution_minutes": settings.low_resolution_minutes,
            },
        )
        base = self.reported_at or now_datetime()
        self.response_due_at = add_to_date(base, minutes=response)
        self.resolution_due_at = add_to_date(base, minutes=resolution)
        self.sla_status = "On Track"

    def _set_repeat_count(self):
        filters = {"property": self.property, "name": ("!=", self.name or ""), "status": ("!=", "Cancelled")}
        if self.problem_code:
            filters["problem_code"] = self.problem_code
        else:
            filters["problem_category"] = self.problem_category
            if self.room:
                filters["room"] = self.room
        self.similar_occurrence_count = frappe.db.count("Hotel Maintenance Ticket", filters) + 1
        threshold = frappe.db.get_single_value("Hotel PMS Settings", "sop_repeat_threshold") or 3
        self.recurring_problem = 1 if self.similar_occurrence_count >= int(threshold) else 0

    def validate(self):
        validate_photo_fields(self, {"before_photo", "after_photo"})
        self._set_repeat_count()
        if self.safety_risk and not self.priority.startswith("Critical"):
            self.priority = "Critical - Safety / Spreading Damage"
        if self.guest_impact in ("Guest Cannot Use Facility", "Room Move Required") and self.priority in ("Medium", "Low"):
            self.priority = "Critical - Guest Complaint"
        old = self.get_doc_before_save() if not self.is_new() else None
        if self.is_new() or not self.response_due_at or not self.resolution_due_at or (old and old.priority != self.priority):
            self._set_sla_deadlines()
        self.sla_status = calculate_sla_status(
            now=now_datetime(),
            response_due_at=get_datetime(self.response_due_at) if self.response_due_at else None,
            resolution_due_at=get_datetime(self.resolution_due_at) if self.resolution_due_at else None,
            acknowledged_at=get_datetime(self.acknowledged_at) if self.acknowledged_at else None,
            resolved_at=get_datetime(self.resolved_at) if self.resolved_at else None,
        )
        if self.acknowledged_at and self.reported_at:
            self.response_minutes = max((get_datetime(self.acknowledged_at) - get_datetime(self.reported_at)).total_seconds() / 60, 0)
        if self.resolved_at and self.reported_at:
            self.resolution_minutes = max((get_datetime(self.resolved_at) - get_datetime(self.reported_at)).total_seconds() / 60, 0)
