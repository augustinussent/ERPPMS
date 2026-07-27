from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, now_datetime

from hotel_pms.media import validate_photo_fields


class HotelLostAndFound(Document):
    def before_insert(self):
        self.found_at = self.found_at or now_datetime()
        self.found_by = self.found_by or frappe.session.user
        if not self.disposal_date:
            retention_days = frappe.db.get_single_value("Hotel PMS Settings", "lost_found_retention_days") or 90
            self.disposal_date = add_days(self.found_at.date(), int(retention_days))
        if not self.custody_logs:
            self.append(
                "custody_logs",
                {
                    "event_at": self.found_at,
                    "action": "Found",
                    "from_user": self.found_by,
                    "to_user": self.found_by,
                    "location": self.found_location,
                    "notes": "Initial lost-and-found record.",
                },
            )

    def validate(self):
        validate_photo_fields(self, {"item_photo"})
        if self.sensitive_item and self.status == "Disposed":
            frappe.throw("Sensitive or high-value items require management handling and cannot be disposed through a normal status change.")
