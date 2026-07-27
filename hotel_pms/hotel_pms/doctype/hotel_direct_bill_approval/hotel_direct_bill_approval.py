import frappe
from frappe import _
from frappe.model.document import Document


class HotelDirectBillApproval(Document):
    def validate(self):
        if self.requested_amount <= 0:
            frappe.throw(_("Requested amount must be greater than zero."))
        reservation_property = frappe.db.get_value("Hotel Reservation", self.reservation, "property")
        account_property = frappe.db.get_value("Hotel City Ledger Account", self.city_ledger_account, "property")
        if reservation_property != account_property:
            frappe.throw(_("Reservation and city-ledger account belong to different properties."))
        if self.approved_amount and self.approved_amount < 0:
            frappe.throw(_("Approved amount cannot be negative."))
