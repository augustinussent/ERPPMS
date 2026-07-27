import frappe


def get_context(context):
    context.no_cache = 1
    context.no_breadcrumbs = 1
    context.sitemap = 1
    context.property_slug = frappe.form_dict.get("property") or ""
    context.title = "Book Direct"
    if context.property_slug:
        row = frappe.db.get_value(
            "Hotel Property",
            {"public_slug": context.property_slug, "enabled": 1, "public_booking_enabled": 1},
            ["public_meta_title", "public_meta_description", "public_name", "property_name"],
            as_dict=True,
        )
        if row:
            context.title = row.public_meta_title or row.public_name or row.property_name
            context.metatags = {"description": row.public_meta_description or "Direct hotel booking"}
    return context
