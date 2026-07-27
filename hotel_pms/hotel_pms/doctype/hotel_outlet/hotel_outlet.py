from frappe.model.document import Document


class HotelOutlet(Document):
    def validate(self):
        import re, frappe
        if self.public_slug and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", self.public_slug):
            frappe.throw("Public Slug must contain lowercase letters, numbers, and hyphens only.")
        if not self.company and self.property:
            self.company = frappe.db.get_value("Hotel Property", self.property, "company")
