from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from hotel_pms.setup_front_office import _upsert_print_format
from hotel_pms.setup_services import KOT_HTML, KOT_PRINT_FORMAT


def setup_fnb_depth() -> None:
    create_custom_fields({
        "Stock Entry": [
            {"fieldname":"custom_hotel_sync_key","label":"Hotel PMS Sync Key","fieldtype":"Data","insert_after":"project","read_only":1,"hidden":1,"unique":1,"no_copy":1},
            {"fieldname":"custom_hotel_kitchen_ticket","label":"Hotel Kitchen Ticket","fieldtype":"Link","options":"Hotel Kitchen Ticket","insert_after":"custom_hotel_sync_key","read_only":1,"no_copy":1},
            {"fieldname":"custom_hotel_restaurant_order","label":"Hotel Restaurant Order","fieldtype":"Link","options":"Hotel Restaurant Order","insert_after":"custom_hotel_kitchen_ticket","read_only":1,"no_copy":1},
        ]
    }, update=True)
    _upsert_print_format(KOT_PRINT_FORMAT, "Hotel Kitchen Ticket", KOT_HTML)
    for doctype, fields in {
        "Hotel Kitchen Ticket": ["outlet", "status", "target_ready_at"],
        "Hotel Menu Import Batch": ["property", "outlet", "status"],
        "Hotel Outlet Menu Item": ["outlet", "recipe_enabled"],
    }.items():
        try:
            frappe.db.add_index(doctype, fields)
        except Exception:
            pass
