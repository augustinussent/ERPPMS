from frappe.model.document import Document


class HotelOutletMenuItem(Document):
    def validate(self):
        import frappe
        if self.rate < 0:
            frappe.throw("Rate cannot be negative.")
        duplicate = frappe.db.exists("Hotel Outlet Menu Item", {"outlet": self.outlet, "item_code": self.item_code, "name": ["!=", self.name]})
        if duplicate:
            frappe.throw("The ERPNext Item is already configured for this outlet.")
        if not self.menu_name and self.item_code:
            self.menu_name = frappe.db.get_value("Item", self.item_code, "item_name")
