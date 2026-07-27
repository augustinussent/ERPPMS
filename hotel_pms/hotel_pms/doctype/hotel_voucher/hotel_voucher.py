import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class HotelVoucher(Document):
    def validate(self):
        self.voucher_code = (self.voucher_code or "").strip().upper()
        if self.discount_value <= 0:
            frappe.throw(_("Discount value must be greater than zero."))
        if self.discount_type == "Percentage" and self.discount_value > 100:
            frappe.throw(_("Percentage discount cannot exceed 100%."))
        if self.maximum_discount and self.maximum_discount < 0:
            frappe.throw(_("Maximum discount cannot be negative."))
        for start_field, end_field, label in (
            ("booking_from", "booking_to", _("booking period")),
            ("stay_from", "stay_to", _("stay period")),
        ):
            start = self.get(start_field)
            end = self.get(end_field)
            if start and end and getdate(end) < getdate(start):
                frappe.throw(_("The end of the {0} cannot be before its start.").format(label))
        if self.room_type and frappe.db.get_value("Hotel Room Type", self.room_type, "property") != self.property:
            frappe.throw(_("Voucher room type belongs to another property."))
        if self.rate_plan:
            plan = frappe.db.get_value("Hotel Rate Plan", self.rate_plan, ["property", "room_type"], as_dict=True)
            if not plan or plan.property != self.property:
                frappe.throw(_("Voucher rate plan belongs to another property."))
            if self.room_type and plan.room_type != self.room_type:
                frappe.throw(_("Voucher rate plan does not match the selected room type."))
