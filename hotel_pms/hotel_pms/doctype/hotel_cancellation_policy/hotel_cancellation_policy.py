import frappe
from frappe import _
from frappe.model.document import Document


class HotelCancellationPolicy(Document):
    def validate(self):
        if (self.free_cancellation_days or 0) < 0:
            frappe.throw(_("Free cancellation days cannot be negative."))
        if self.fee_type != "None" or self.no_show_fee_type != "None":
            if not self.fee_item:
                frappe.throw(_("ERPNext Fee Item is required when cancellation or no-show fees may be charged."))
        if self.fee_type == "Percentage" and not 0 <= (self.fee_value or 0) <= 100:
            frappe.throw(_("Cancellation percentage must be between 0 and 100."))
        if self.no_show_fee_type == "Percentage" and not 0 <= (self.no_show_fee_value or 0) <= 100:
            frappe.throw(_("No-show percentage must be between 0 and 100."))
