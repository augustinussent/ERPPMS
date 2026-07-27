from frappe.model.document import Document


class HotelMenuImportBatch(Document):
    def validate(self):
        import frappe
        previous = self.get_doc_before_save() if not self.is_new() else None
        if previous and previous.status in ("Committed", "Partially Failed"):
            protected = (previous.outlet, previous.property, previous.request_key)
            if protected != (self.outlet, self.property, self.request_key):
                frappe.throw("Committed menu-import identity fields cannot be changed.")
