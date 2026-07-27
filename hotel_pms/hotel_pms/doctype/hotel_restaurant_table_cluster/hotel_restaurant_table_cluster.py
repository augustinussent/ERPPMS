import frappe
from frappe.model.document import Document


class HotelRestaurantTableCluster(Document):
    def validate(self):
        order = frappe.get_doc("Hotel Restaurant Order", self.restaurant_order)
        if order.property != self.property or order.outlet != self.outlet:
            frappe.throw("Table Cluster must match the Restaurant Order property and outlet.")
        tables = [row.table for row in self.members]
        if len(tables) != len(set(tables)):
            frappe.throw("Table Cluster members must be unique.")
        if len(tables) < 2:
            frappe.throw("Table Cluster requires at least two tables.")
