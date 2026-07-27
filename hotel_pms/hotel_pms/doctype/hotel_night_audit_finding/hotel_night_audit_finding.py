import frappe
from frappe import _
from frappe.model.document import Document
class HotelNightAuditFinding(Document):
    def validate(self):
        if self.status in ("Resolved","False Positive") and not self.resolution_notes:
            frappe.throw(_("Resolution Notes are required when closing a finding."))
