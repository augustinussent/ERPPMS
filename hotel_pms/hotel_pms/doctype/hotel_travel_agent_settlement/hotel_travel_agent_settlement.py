import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class HotelTravelAgentSettlement(Document):
    def validate(self):
        if getdate(self.period_to) < getdate(self.period_from):
            frappe.throw(_("Period To cannot be before Period From."))
        contract = frappe.get_doc("Hotel Travel Agent Contract", self.contract)
        if contract.property != self.property:
            frappe.throw(_("Contract belongs to another property."))
        self.supplier = contract.travel_agent
        seen = set()
        for row in self.lines:
            if row.reservation in seen:
                frappe.throw(_("Reservation {0} appears more than once.").format(row.reservation))
            seen.add(row.reservation)
        self.total_commission = sum(flt(row.commission_amount) for row in self.lines)
