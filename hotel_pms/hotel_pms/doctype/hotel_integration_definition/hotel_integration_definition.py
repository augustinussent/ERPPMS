import frappe
from frappe import _
from frappe.model.document import Document
class HotelIntegrationDefinition(Document):
    def validate(self):
        if self.maturity_status == "Shipped" and not self.enabled_in_product:
            frappe.throw(_("A Shipped integration must have an in-product path."))
        if self.financial_behavior == "ERPNext Native" and self.category not in ("ERP & Accounting","Payments"):
            frappe.throw(_("ERPNext Native financial behavior is only valid for accounting or payment integrations."))
