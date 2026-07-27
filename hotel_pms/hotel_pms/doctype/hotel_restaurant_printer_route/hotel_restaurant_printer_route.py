import frappe
from frappe.model.document import Document


class HotelRestaurantPrinterRoute(Document):
    def validate(self):
        outlet = frappe.get_doc("Hotel Outlet", self.outlet)
        if outlet.property != self.property:
            frappe.throw("Printer Route property must match the outlet property.")
        if self.production_unit:
            unit = frappe.get_doc("Hotel Kitchen Production Unit", self.production_unit)
            if unit.outlet != self.outlet or unit.property != self.property:
                frappe.throw("Printer Route Production Unit must belong to the same outlet and property.")
        if (self.copies or 0) < 1 or (self.copies or 0) > 10:
            frappe.throw("Printer copies must be between 1 and 10.")
        if self.print_format:
            doc_type = frappe.db.get_value("Print Format", self.print_format, "doc_type")
            if self.purpose == "KOT" and doc_type != "Hotel Kitchen Ticket":
                frappe.throw("KOT printer route requires a Hotel Kitchen Ticket Print Format.")
            if self.purpose == "Bill" and doc_type not in ("POS Invoice", "Sales Invoice"):
                frappe.throw("Bill printer route requires a POS Invoice or Sales Invoice Print Format.")
            if self.purpose == "Both":
                frappe.throw("A route with purpose Both must use the document default Print Format.")
