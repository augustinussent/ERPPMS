
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class HotelTravelAgentContract(Document):
    def validate(self):
        if getdate(self.valid_to) < getdate(self.valid_from):
            frappe.throw(_("Valid To cannot be before Valid From."))
        if self.pricing_basis == "Gross Rate with Commission" and not self.commission_rate:
            frappe.throw(_("Commission percentage is required for gross-rate contracts."))
        if self.pricing_basis == "Net Rate" and not self.net_rate_discount:
            frappe.throw(_("Net-rate discount is required for net-rate contracts."))
