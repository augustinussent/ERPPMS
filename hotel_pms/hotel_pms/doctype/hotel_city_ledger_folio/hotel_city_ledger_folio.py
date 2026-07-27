import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class HotelCityLedgerFolio(Document):
    def validate(self):
        account = frappe.get_doc("Hotel City Ledger Account", self.city_ledger_account)
        if account.property != self.property:
            frappe.throw(_("City ledger account belongs to another property."))
        if account.status != "Active":
            frappe.throw(_("City ledger account must be active."))
        self.billing_customer = account.customer
        self.total_charges = sum(flt(row.amount) for row in self.charges if not row.is_void)
