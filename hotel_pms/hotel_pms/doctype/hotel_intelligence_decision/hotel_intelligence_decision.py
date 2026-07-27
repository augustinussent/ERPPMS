import frappe
from frappe.model.document import Document
class HotelIntelligenceDecision(Document):
    def before_save(self):
        if self.is_new() or self.flags.get("intelligence_internal_update"): return
        frappe.throw("Use governed intelligence actions to change decision status.", frappe.PermissionError)
