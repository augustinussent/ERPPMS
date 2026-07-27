import frappe
from frappe.model.document import Document


class HotelKitchenProductionUnit(Document):
    def validate(self):
        outlet = frappe.get_doc("Hotel Outlet", self.outlet)
        if outlet.property != self.property:
            frappe.throw("Production Unit property must match the outlet property.")
        existing = frappe.db.get_value("Hotel Kitchen Production Unit", {"outlet": self.outlet, "unit_name": self.unit_name, "name": ["!=", self.name or ""]}, "name")
        if existing:
            frappe.throw("Production Unit name must be unique within an outlet.")
