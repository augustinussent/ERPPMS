from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def setup_restaurant_controls() -> None:
    fields = []
    for dt in ("POS Opening Entry", "POS Closing Entry"):
        fields_map = [
            {"fieldname": "custom_hotel_cashier_shift", "label": "Hotel Cashier Shift", "fieldtype": "Link", "options": "Hotel Cashier Shift", "insert_after": "pos_profile", "read_only": 1},
            {"fieldname": "custom_hotel_property", "label": "Hotel Property", "fieldtype": "Link", "options": "Hotel Property", "insert_after": "custom_hotel_cashier_shift", "read_only": 1},
            {"fieldname": "custom_hotel_outlet", "label": "Hotel Outlet", "fieldtype": "Link", "options": "Hotel Outlet", "insert_after": "custom_hotel_property", "read_only": 1},
        ]
        create_custom_fields({dt: fields_map}, update=True)
    indexes = {
        "Hotel Kitchen Ticket": [["restaurant_order", "revision_no"], ["outlet", "status", "target_ready_at"], ["request_key"]],
        "Hotel Restaurant Print Job": [["status", "attempts"], ["request_key"]],
        "Hotel Restaurant Alert": [["property", "status", "severity"], ["fingerprint"]],
        "Hotel Restaurant Table Cluster": [["restaurant_order", "status"], ["request_key"]],
        "Hotel Cashier Shift": [["outlet", "cashier", "status"], ["pos_opening_entry"], ["pos_closing_entry"]],
    }
    for doctype, definitions in indexes.items():
        if not frappe.db.table_exists(doctype):
            continue
        for definition in definitions:
            try:
                frappe.db.add_index(doctype, definition)
            except Exception:
                pass
    _backfill_production_units()


def _backfill_production_units() -> None:
    if not frappe.db.table_exists("Hotel Kitchen Production Unit") or not frappe.db.table_exists("Hotel Outlet Menu Item"):
        return
    menus = frappe.get_all(
        "Hotel Outlet Menu Item",
        filters={"kitchen_station": ["is", "set"]},
        fields=["name", "outlet", "kitchen_station", "production_unit"],
        limit_page_length=0,
    )
    cache = {}
    for menu in menus:
        if menu.production_unit:
            continue
        key = (menu.outlet, (menu.kitchen_station or "Main Kitchen").strip())
        unit_name = cache.get(key) or frappe.db.get_value(
            "Hotel Kitchen Production Unit", {"outlet": key[0], "unit_name": key[1]}, "name"
        )
        if not unit_name:
            outlet = frappe.db.get_value("Hotel Outlet", key[0], ["property", "kds_late_minutes"], as_dict=True)
            if not outlet:
                continue
            unit = frappe.get_doc({
                "doctype": "Hotel Kitchen Production Unit",
                "property": outlet.property,
                "outlet": key[0],
                "unit_name": key[1],
                "warning_minutes": outlet.kds_late_minutes or 15,
                "enabled": 1,
            })
            unit.insert(ignore_permissions=True)
            unit_name = unit.name
        cache[key] = unit_name
        frappe.db.set_value("Hotel Outlet Menu Item", menu.name, "production_unit", unit_name, update_modified=False)
