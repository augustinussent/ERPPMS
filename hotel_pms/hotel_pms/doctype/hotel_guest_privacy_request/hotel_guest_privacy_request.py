import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, getdate, now_datetime, cint


class HotelGuestPrivacyRequest(Document):
    def before_insert(self):
        self.requested_at = now_datetime()
        self.eligible_after = add_days(
            getdate(), cint(frappe.db.get_single_value("Hotel PMS Settings", "privacy_request_cooling_days") or 7)
        )

    def validate(self):
        old = self.get_doc_before_save() if not self.is_new() else None
        if old and old.status != self.status and self.status in ("Approved", "Rejected", "Completed"):
            frappe.only_for(["System Manager", "Hotel Manager", "Accounts Manager"])
        if self.status == "Approved" and not self.approved_by:
            self.approved_by = frappe.session.user
            self.approved_at = now_datetime()
