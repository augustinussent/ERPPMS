import frappe
from frappe.model.document import Document
class HotelIntelligenceRun(Document):
    def before_save(self):
        if self.is_new() or self.flags.get("intelligence_internal_update"): return
        frappe.throw("Intelligence run records are immutable evidence.", frappe.PermissionError)
    def on_trash(self):
        if not self.flags.get("intelligence_internal_update"):
            frappe.throw("Intelligence run records are immutable evidence.", frappe.PermissionError)
