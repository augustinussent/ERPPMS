
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class HotelRateApproval(Document):
    def validate(self):
        if self.requested_rate >= self.floor_rate:
            frappe.throw(_("Approval is only required when the requested rate is below the floor rate."))
        if self.status == "Approved" and not self.approved_by:
            self.approved_by = frappe.session.user
            self.approved_at = now_datetime()
