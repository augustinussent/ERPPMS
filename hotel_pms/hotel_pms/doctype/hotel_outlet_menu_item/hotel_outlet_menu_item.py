from frappe.model.document import Document


class HotelOutletMenuItem(Document):
    def validate(self):
        import frappe
        from frappe.utils import flt
        if self.rate < 0:
            frappe.throw("Rate cannot be negative.")
        duplicate = frappe.db.exists("Hotel Outlet Menu Item", {"outlet": self.outlet, "item_code": self.item_code, "name": ["!=", self.name]})
        if duplicate:
            frappe.throw("The ERPNext Item is already configured for this outlet.")
        if not self.menu_name and self.item_code:
            self.menu_name = frappe.db.get_value("Item", self.item_code, "item_name")
        if self.production_unit:
            unit = frappe.get_doc("Hotel Kitchen Production Unit", self.production_unit)
            if unit.outlet != self.outlet or not unit.enabled:
                frappe.throw("Production Unit must be enabled and belong to the selected outlet.")
            self.kitchen_station = unit.unit_name
        seen = set()
        for row in self.recipe_items:
            if not row.ingredient_item:
                frappe.throw("Every recipe row requires an ERPNext ingredient Item.")
            if row.ingredient_item in seen:
                frappe.throw(f"Ingredient {row.ingredient_item} appears more than once in the recipe.")
            seen.add(row.ingredient_item)
            if flt(row.qty_per_menu_unit) <= 0:
                frappe.throw(f"Ingredient {row.ingredient_item} requires a positive quantity.")
            item = frappe.db.get_value("Item", row.ingredient_item, ["is_stock_item", "stock_uom", "disabled"], as_dict=True)
            if not item or item.disabled or not item.is_stock_item:
                frappe.throw(f"Ingredient {row.ingredient_item} must be an enabled ERPNext stock Item.")
            row.stock_uom = item.stock_uom
            if row.source_warehouse:
                outlet_company = frappe.db.get_value("Hotel Outlet", self.outlet, "company")
                warehouse_company = frappe.db.get_value("Warehouse", row.source_warehouse, "company")
                if warehouse_company and warehouse_company != outlet_company:
                    frappe.throw(f"Recipe warehouse {row.source_warehouse} belongs to another company.")
        if self.recipe_enabled and not self.recipe_items:
            frappe.throw("Add at least one ingredient before enabling recipe consumption.")
