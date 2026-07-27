import json
import frappe
from frappe import _
from frappe.model.document import Document
from hotel_pms.localization.registry import get_localization_context,validate_tax_profile_mapping

class HotelTaxProfile(Document):
    def validate(self):
        if self.service_charge_rate < 0 or self.tax_rate < 0:frappe.throw(_("Rates cannot be negative."))
        if self.service_charge_rate > 100 or self.tax_rate > 100:frappe.throw(_("Service-charge and tax percentages cannot exceed 100%."))
        messages=validate_tax_profile_mapping(self)
        context=get_localization_context(self.property,self.transaction_scope or "All")
        self.localization_context_preview=json.dumps(context,ensure_ascii=False)
        if messages:frappe.msgprint("<br>".join(_(x) for x in messages),alert=True)
