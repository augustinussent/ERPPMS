from frappe.model.document import Document


class HotelDiningArea(Document):
    def validate(self):
        import frappe
        duplicate = frappe.db.exists("Hotel Dining Area", {"outlet": self.outlet, "area_name": self.area_name, "name": ["!=", self.name]})
        if duplicate:
            frappe.throw("Area name must be unique within the outlet.")
