import frappe
from frappe import _
from frappe.model.document import Document


class HotelGuestActionLog(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw(_("Guest action logs are append-only."))
