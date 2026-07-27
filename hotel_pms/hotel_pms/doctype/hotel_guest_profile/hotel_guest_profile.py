
from __future__ import annotations
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, getdate, now_datetime

class HotelGuestProfile(Document):
    def validate(self):
        if self.status == "Anonymized":
            self.marketing_consent = 0
            self.privacy_status = "Anonymized"
        if not self.retention_until:
            days = cint(frappe.db.get_single_value("Hotel PMS Settings", "privacy_retention_days") or 1825)
            self.retention_until = add_days(getdate(), days)

    def on_update(self):
        if frappe.get_meta("Customer").has_field("custom_hotel_guest_profile"):
            current = frappe.db.get_value("Customer", self.customer, "custom_hotel_guest_profile")
            if current != self.name:
                frappe.db.set_value("Customer", self.customer, "custom_hotel_guest_profile", self.name, update_modified=False)
