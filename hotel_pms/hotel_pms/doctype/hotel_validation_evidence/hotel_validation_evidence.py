import frappe
from frappe.model.document import Document


class HotelValidationEvidence(Document):
    def before_save(self):
        if self.is_new() or self.flags.get("validation_internal_update"):
            return
        frappe.throw("Validation records are immutable and must be recreated, not edited.", frappe.PermissionError)

    def on_trash(self):
        if not self.flags.get("validation_internal_update"):
            frappe.throw("Validation records are immutable audit evidence.", frappe.PermissionError)
