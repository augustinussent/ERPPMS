import frappe
from frappe import _
from frappe.model.document import Document
class HotelGuestMessage(Document):
    def before_delete(self):
        if "System Manager" not in frappe.get_roles():
            frappe.throw(_("Guest message records are audit records and cannot be deleted."),frappe.PermissionError)
