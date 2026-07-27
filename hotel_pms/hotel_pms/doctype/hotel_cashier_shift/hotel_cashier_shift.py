
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class HotelCashierShift(Document):
    def before_insert(self):
        if not self.opened_at:
            self.opened_at = now_datetime()
        if not self.cashier:
            self.cashier = frappe.session.user
    def validate(self):
        if self.counted_cash is not None:
            self.variance = (self.counted_cash or 0) - (self.expected_cash or 0)
        if self.status == "Closed" and self.variance and not self.variance_reason:
            frappe.throw(_("Variance reason is required before closing a shift with a difference."))
