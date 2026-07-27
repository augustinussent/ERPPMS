from frappe.model.document import Document


class HotelGuestExperience(Document):
    def validate(self):
        import frappe
        if self.duration_minutes <= 0 or self.capacity <= 0 or self.price < 0:
            frappe.throw("Duration and capacity must be positive; price cannot be negative.")
