import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class HotelRatePlan(Document):
    def validate(self):
        if self.valid_from and self.valid_to and getdate(self.valid_to) < getdate(self.valid_from):
            frappe.throw(_("Valid To cannot be before Valid From."))
        if self.max_stay and self.min_stay and self.max_stay < self.min_stay:
            frappe.throw(_("Maximum stay cannot be below minimum stay."))
        if self.maximum_advance_days and self.minimum_advance_days and self.maximum_advance_days < self.minimum_advance_days:
            frappe.throw(_("Maximum advance days cannot be below minimum advance days."))
        if self.base_rate_plan:
            if self.base_rate_plan == self.name:
                frappe.throw(_("A rate plan cannot derive from itself."))
            parent = frappe.db.get_value("Hotel Rate Plan", self.base_rate_plan, ["property", "room_type"], as_dict=True)
            if not parent or parent.property != self.property or parent.room_type != self.room_type:
                frappe.throw(_("Base rate plan must belong to the same property and room type."))
            if not self.derived_adjustment_type:
                frappe.throw(_("Select a derived-rate adjustment type."))
        elif not self.rate:
            frappe.throw(_("A base rate is required when no base rate plan is selected."))
