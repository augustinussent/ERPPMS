from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from hotel_pms.media import validate_photo_fields


class HotelSOPCandidate(Document):
    def validate(self):
        validate_photo_fields(self, {"before_photo", "after_photo", "reference_photo"})
        old = self.get_doc_before_save() if not self.is_new() else None
        if old and old.status != self.status:
            if self.status in ("Approved", "Published"):
                frappe.only_for(["System Manager", "Hotel Manager", "Engineering Supervisor"])
                if not self.engineering_reviewer or not self.housekeeping_reviewer:
                    frappe.throw("Engineering and Housekeeping reviewers are required before approval or publication.")
                self.approved_by = self.approved_by or frappe.session.user
                self.approved_at = self.approved_at or now_datetime()
            if self.status == "Published":
                if not self.published_reference:
                    frappe.throw("Published SOP Reference is required before publication.")
                self.published_at = self.published_at or now_datetime()
