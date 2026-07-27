import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class HotelRateSeason(Document):
    def validate(self):
        if getdate(self.valid_to) < getdate(self.valid_from):
            frappe.throw(_("Valid To cannot be before Valid From."))
        if self.room_type:
            room_property = frappe.db.get_value("Hotel Room Type", self.room_type, "property")
            if room_property != self.property:
                frappe.throw(_("Room type belongs to another property."))
        if self.rate_plan:
            plan = frappe.db.get_value("Hotel Rate Plan", self.rate_plan, ["property", "room_type"], as_dict=True)
            if not plan or plan.property != self.property:
                frappe.throw(_("Rate plan belongs to another property."))
            if self.room_type and plan.room_type != self.room_type:
                frappe.throw(_("Rate plan does not belong to the selected room type."))
        if self.adjustment_type == "Percentage" and self.adjustment_value <= -100:
            frappe.throw(_("Percentage adjustment must remain above -100%."))
        if self.adjustment_type == "Fixed Rate" and self.adjustment_value < 0:
            frappe.throw(_("Fixed rate cannot be negative."))
