
from __future__ import annotations
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime

class HotelGuestAccessToken(Document):
    def validate(self):
        if not self.reservation and not self.customer:
            frappe.throw(_("A guest token requires a reservation or customer."))
        if self.expires_at and get_datetime(self.expires_at) <= now_datetime() and self.status == "Active":
            self.status = "Expired"
