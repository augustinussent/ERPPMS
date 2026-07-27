from frappe.model.document import Document


class HotelLaundryRate(Document):
    def validate(self):
        import frappe
        if self.rate < 0 or self.turnaround_hours <= 0:
            frappe.throw("Rate cannot be negative and turnaround must be positive.")
        duplicate = frappe.db.exists("Hotel Laundry Rate", {"property": self.property, "item_code": self.item_code, "service_type": self.service_type, "name": ["!=", self.name]})
        if duplicate:
            frappe.throw("Laundry rate already exists for this item and service type.")
