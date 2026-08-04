from __future__ import annotations

import frappe


MENU_ITEMS = [
    # Makanan & Snack
    {"code": "FOOD-NASGOR", "name": "Nasi Goreng", "group": "Food", "rate": 35000, "station": "Hot Kitchen", "prep": 15},
    {"code": "FOOD-MIEGOR", "name": "Mie Goreng", "group": "Food", "rate": 35000, "station": "Hot Kitchen", "prep": 15},
    {"code": "FOOD-FRIES", "name": "French Fries", "group": "Food", "rate": 20000, "station": "Hot Kitchen", "prep": 10},
    {"code": "FOOD-CIRENG", "name": "Cireng Bumbu Rujak", "group": "Food", "rate": 17000, "station": "Hot Kitchen", "prep": 10},
    {"code": "FOOD-ROTI-COK", "name": "Roti Bakar Cokelat", "group": "Food", "rate": 15000, "station": "Hot Kitchen", "prep": 10},
    {"code": "FOOD-ROTI-KEJU", "name": "Roti Bakar Keju", "group": "Food", "rate": 15000, "station": "Hot Kitchen", "prep": 10},
    {"code": "FOOD-JAGUNG-MANIS", "name": "Jagung Bakar Manis", "group": "Food", "rate": 12000, "station": "Hot Kitchen", "prep": 12},
    {"code": "FOOD-JAGUNG-PEDAS", "name": "Jagung Bakar Pedas", "group": "Food", "rate": 12000, "station": "Hot Kitchen", "prep": 12},
    {"code": "FOOD-JAGUNG-MENTEGA", "name": "Jagung Bakar Mentega", "group": "Food", "rate": 12000, "station": "Hot Kitchen", "prep": 12},
    {"code": "FOOD-DONAT", "name": "Donat Gula", "group": "Food", "rate": 8000, "station": "Pastry / Snack", "prep": 5},

    # Dimsum
    {"code": "DIM-UDANG-KEJU", "name": "Udang Keju (3)", "group": "Dimsum", "rate": 18000, "station": "Dimsum Station", "prep": 12},
    {"code": "DIM-DRUMSTICK", "name": "Drumstick (3)", "group": "Dimsum", "rate": 18000, "station": "Dimsum Station", "prep": 12},
    {"code": "DIM-UDANG-RAMBUTAN", "name": "Udang Rambutan (3)", "group": "Dimsum", "rate": 18000, "station": "Dimsum Station", "prep": 12},
    {"code": "DIM-SIOMAY-AYAM", "name": "Siomay Ayam (3)", "group": "Dimsum", "rate": 15000, "station": "Dimsum Station", "prep": 10},
    {"code": "DIM-SIOMAY-MOZZA", "name": "Siomay Mozza (3)", "group": "Dimsum", "rate": 15000, "station": "Dimsum Station", "prep": 10},
    {"code": "DIM-GYOZA", "name": "Gyoza (3)", "group": "Dimsum", "rate": 15000, "station": "Dimsum Station", "prep": 12},

    # Coffee (Black)
    {"code": "COF-ESPRESSO-HOT", "name": "Espresso Hot", "group": "Coffee", "rate": 18000, "station": "Bar / Beverage", "prep": 5},
    {"code": "COF-AMERICANO-HOT", "name": "Americano Hot", "group": "Coffee", "rate": 18000, "station": "Bar / Beverage", "prep": 5},
    {"code": "COF-AMERICANO-ICE", "name": "Americano Ice", "group": "Coffee", "rate": 20000, "station": "Bar / Beverage", "prep": 5},
    {"code": "COF-LONGBLCK-HOT", "name": "Longblack Hot", "group": "Coffee", "rate": 25000, "station": "Bar / Beverage", "prep": 5},
    {"code": "COF-LONGBLCK-ICE", "name": "Longblack Ice", "group": "Coffee", "rate": 27000, "station": "Bar / Beverage", "prep": 5},
    {"code": "COF-SIGNATURE-HOT", "name": "Signature Hot", "group": "Coffee", "rate": 25000, "station": "Bar / Beverage", "prep": 7},
    {"code": "COF-SIGNATURE-ICE", "name": "Signature Ice", "group": "Coffee", "rate": 28000, "station": "Bar / Beverage", "prep": 7},

    # Coffee (White)
    {"code": "COF-AREN-HOT", "name": "RR Gula Aren Hot", "group": "Coffee", "rate": 23000, "station": "Bar / Beverage", "prep": 5},
    {"code": "COF-AREN-ICE", "name": "RR Gula Aren Ice", "group": "Coffee", "rate": 25000, "station": "Bar / Beverage", "prep": 5},
    {"code": "COF-CAPPUCCINO-HOT", "name": "Cappuccino Hot", "group": "Coffee", "rate": 25000, "station": "Bar / Beverage", "prep": 7},
    {"code": "COF-CAPPUCCINO-ICE", "name": "Cappuccino Ice", "group": "Coffee", "rate": 27000, "station": "Bar / Beverage", "prep": 7},
    {"code": "COF-LATTE-HOT", "name": "Latte Hot", "group": "Coffee", "rate": 23000, "station": "Bar / Beverage", "prep": 7},
    {"code": "COF-LATTE-ICE", "name": "Latte Ice", "group": "Coffee", "rate": 25000, "station": "Bar / Beverage", "prep": 7},
    {"code": "COF-CARAMEL-HOT", "name": "Caramel Latte Hot", "group": "Coffee", "rate": 25000, "station": "Bar / Beverage", "prep": 7},
    {"code": "COF-CARAMEL-ICE", "name": "Caramel Latte Ice", "group": "Coffee", "rate": 27000, "station": "Bar / Beverage", "prep": 7},

    # Non-Coffee
    {"code": "NON-CHOCOLATE-HOT", "name": "Chocolate Hot", "group": "Non-Coffee", "rate": 23000, "station": "Bar / Beverage", "prep": 5},
    {"code": "NON-CHOCOLATE-ICE", "name": "Chocolate Ice", "group": "Non-Coffee", "rate": 25000, "station": "Bar / Beverage", "prep": 5},
    {"code": "NON-TEA-HOT", "name": "Tea Hot", "group": "Non-Coffee", "rate": 15000, "station": "Bar / Beverage", "prep": 5},
    {"code": "NON-TEA-ICE", "name": "Tea Ice", "group": "Non-Coffee", "rate": 17000, "station": "Bar / Beverage", "prep": 5},
    {"code": "NON-MILKTEA-HOT", "name": "Milk Tea Hot", "group": "Non-Coffee", "rate": 17000, "station": "Bar / Beverage", "prep": 5},
    {"code": "NON-MILKTEA-ICE", "name": "Milk Tea Ice", "group": "Non-Coffee", "rate": 19000, "station": "Bar / Beverage", "prep": 5},
    {"code": "NON-MATCHA-HOT", "name": "Matcha Latte Hot", "group": "Non-Coffee", "rate": 23000, "station": "Bar / Beverage", "prep": 5},
    {"code": "NON-MATCHA-ICE", "name": "Matcha Latte Ice", "group": "Non-Coffee", "rate": 25000, "station": "Bar / Beverage", "prep": 5},

    # Smoothies & Milkshake
    {"code": "SMO-MANGO", "name": "Tropical Mango", "group": "Beverage", "rate": 28000, "station": "Bar / Beverage", "prep": 8},
    {"code": "SMO-BERRY", "name": "Berry Blast", "group": "Beverage", "rate": 30000, "station": "Bar / Beverage", "prep": 8},
    {"code": "MILK-CHOCO", "name": "Choco Rindu", "group": "Beverage", "rate": 28000, "station": "Bar / Beverage", "prep": 8},
    {"code": "MILK-BANANA", "name": "Banana Caramel", "group": "Beverage", "rate": 30000, "station": "Bar / Beverage", "prep": 8},
]


@frappe.whitelist()
def seed_rintik_rindu_pos(property_name: str = "Spencer Green Hotel", company: str | None = None) -> dict:
    """Idempotently seed Rintik Rindu Pool Cafe outlet, stations, tables, items, and menu items."""
    frappe.only_for(["System Manager", "Hotel Manager"])
    
    # 1. Resolve Property and Company
    if not frappe.db.exists("Hotel Property", property_name):
        prop_doc = frappe.get_doc({
            "doctype": "Hotel Property",
            "property_name": property_name,
            "property_code": "SGH",
            "country": "Indonesia",
            "currency": "IDR",
        })
        prop_doc.flags.ignore_permissions = True
        prop_doc.insert()

    prop = frappe.get_doc("Hotel Property", property_name)
    company_name = company or prop.company or frappe.db.get_default("company") or frappe.get_all("Company", pluck="name", limit=1)[0]

    # 2. Setup Outlet
    outlet_name = "Rintik Rindu Pool Cafe"
    if not frappe.db.exists("Hotel Outlet", outlet_name):
        outlet_doc = frappe.get_doc({
            "doctype": "Hotel Outlet",
            "outlet_name": outlet_name,
            "property": property_name,
            "company": company_name,
            "outlet_type": "Cafe",
            "enabled": 1,
            "allow_room_posting": 1,
            "allow_qr_ordering": 1,
            "public_slug": "rintik-rindu-cafe",
            "inventory_posting_policy": "ERPNext POS Finished Goods",
            "require_pos_opening_entry": 0,
            "cashier_discount_limit": 10,
        })
        outlet_doc.flags.ignore_permissions = True
        outlet_doc.insert()
    else:
        outlet_doc = frappe.get_doc("Hotel Outlet", outlet_name)

    # 3. Setup Kitchen Production Units
    stations = ["Hot Kitchen", "Dimsum Station", "Bar / Beverage", "Pastry / Snack"]
    unit_map = {}
    for st in stations:
        unit_name = frappe.db.get_value("Hotel Kitchen Production Unit", {"outlet": outlet_name, "unit_name": st}, "name")
        if not unit_name:
            u_doc = frappe.get_doc({
                "doctype": "Hotel Kitchen Production Unit",
                "property": property_name,
                "outlet": outlet_name,
                "unit_name": st,
                "warning_minutes": 15,
                "critical_minutes": 25,
            })
            u_doc.flags.ignore_permissions = True
            u_doc.insert()
            unit_map[st] = u_doc.name
        else:
            unit_map[st] = unit_name

    # 4. Setup Dining Area & Tables
    area_name = "Poolside Area"
    if not frappe.db.exists("Hotel Dining Area", {"outlet": outlet_name, "area_name": area_name}):
        a_doc = frappe.get_doc({
            "doctype": "Hotel Dining Area",
            "property": property_name,
            "outlet": outlet_name,
            "area_name": area_name,
        })
        a_doc.flags.ignore_permissions = True
        a_doc.insert()

    for t_idx in range(1, 11):
        t_name = f"RR-{t_idx:02d}"
        if not frappe.db.exists("Hotel Restaurant Table", {"outlet": outlet_name, "table_name": t_name}):
            t_doc = frappe.get_doc({
                "doctype": "Hotel Restaurant Table",
                "property": property_name,
                "outlet": outlet_name,
                "dining_area": area_name,
                "table_name": t_name,
                "seats": 4,
                "enabled": 1,
            })
            t_doc.flags.ignore_permissions = True
            t_doc.insert()

    # 5. Setup ERPNext Item Groups & Items Master
    item_groups = ["Food", "Dimsum", "Coffee", "Non-Coffee", "Beverage"]
    for ig in item_groups:
        if not frappe.db.exists("Item Group", ig):
            try:
                ig_doc = frappe.get_doc({
                    "doctype": "Item Group",
                    "item_group_name": ig,
                    "is_group": 0,
                    "parent_item_group": "All Item Groups" if frappe.db.exists("Item Group", "All Item Groups") else "",
                })
                ig_doc.flags.ignore_permissions = True
                ig_doc.insert()
            except Exception:
                pass

    created_items = 0
    created_menu_items = 0

    for item_spec in MENU_ITEMS:
        # ERPNext Item
        if not frappe.db.exists("Item", item_spec["code"]):
            try:
                i_doc = frappe.get_doc({
                    "doctype": "Item",
                    "item_code": item_spec["code"],
                    "item_name": item_spec["name"],
                    "item_group": item_spec["group"] if frappe.db.exists("Item Group", item_spec["group"]) else "All Item Groups",
                    "stock_uom": "Nos",
                    "is_stock_item": 0,
                    "is_sales_item": 1,
                    "standard_rate": item_spec["rate"],
                })
                i_doc.flags.ignore_permissions = True
                i_doc.insert()
                created_items += 1
            except Exception:
                pass

        # Hotel Outlet Menu Item
        menu_exists = frappe.db.exists("Hotel Outlet Menu Item", {
            "outlet": outlet_name,
            "item_code": item_spec["code"],
        })
        if not menu_exists:
            m_doc = frappe.get_doc({
                "doctype": "Hotel Outlet Menu Item",
                "outlet": outlet_name,
                "item_code": item_spec["code"],
                "menu_name": item_spec["name"],
                "rate": item_spec["rate"],
                "kitchen_station": item_spec["station"],
                "production_unit": unit_map.get(item_spec["station"]),
                "preparation_minutes": item_spec["prep"],
                "available": 1,
                "allow_qr_ordering": 1,
            })
            m_doc.flags.ignore_permissions = True
            m_doc.insert()
            created_menu_items += 1

    return {
        "status": "success",
        "outlet": outlet_name,
        "total_items_in_catalog": len(MENU_ITEMS),
        "created_items": created_items,
        "created_menu_items": created_menu_items,
        "tables_created": 10,
    }
