import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class HotelCityLedgerAccount(Document):
    def validate(self):
        if self.status == "Active" and not self.approved_by:
            if not ({"System Manager", "Hotel Manager", "Credit Manager", "Accounts Manager"} & set(frappe.get_roles())):
                frappe.throw(_("Credit Manager approval is required to activate a city ledger account."))
            self.approved_by = frappe.session.user
            self.approved_at = now_datetime()
        if self.credit_limit and self.credit_limit < 0:
            frappe.throw(_("Credit limit cannot be negative."))
