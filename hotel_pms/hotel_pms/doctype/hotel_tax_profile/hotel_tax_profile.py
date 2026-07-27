import frappe
from frappe import _
from frappe.model.document import Document


class HotelTaxProfile(Document):
    def validate(self):
        if self.service_charge_rate < 0 or self.tax_rate < 0:
            frappe.throw(_("Rates cannot be negative."))
        if self.service_charge_rate > 100 or self.tax_rate > 100:
            frappe.throw(_("Service-charge and tax percentages cannot exceed 100%."))
        if (self.service_charge_rate or self.tax_rate) and not self.accountant_reviewed:
            frappe.msgprint(
                _("This profile is not marked as reviewed by the hotel accountant or tax adviser."),
                alert=True,
            )
