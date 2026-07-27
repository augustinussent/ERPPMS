from frappe.model.document import Document


class HotelRestaurantTable(Document):
    def before_insert(self):
        import secrets
        if not self.qr_token:
            self.qr_token = secrets.token_urlsafe(24)

    def validate(self):
        import frappe
        if self.seats <= 0:
            frappe.throw("Seats must be greater than zero.")
        if self.dining_area and frappe.db.get_value("Hotel Dining Area", self.dining_area, "outlet") != self.outlet:
            frappe.throw("Dining Area must belong to the selected Outlet.")
