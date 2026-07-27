from frappe.model.document import Document


class HotelOutlet(Document):
    def validate(self):
        import re, frappe
        if self.public_slug and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", self.public_slug):
            frappe.throw("Public Slug must contain lowercase letters, numbers, and hyphens only.")
        if not self.company and self.property:
            self.company = frappe.db.get_value("Hotel Property", self.property, "company")
        if self.inventory_posting_policy == "Recipe Material Issue":
            warehouse = self.recipe_source_warehouse or self.warehouse
            if not warehouse:
                frappe.throw("Recipe Material Issue requires a source warehouse.")
            company = frappe.db.get_value("Warehouse", warehouse, "company")
            if company and company != self.company:
                frappe.throw("Recipe source warehouse must belong to the outlet company.")
        if self.inventory_posting_policy == "ERPNext POS Finished Goods" and self.recipe_stock_entry_mode == "Submit":
            # Prevent a misleading configuration that suggests both stock paths are live.
            self.recipe_stock_entry_mode = "Draft"
