from __future__ import annotations

import frappe

RINTIK_RINDU_MENU = [
    # Makanan & Snack
    {"code": "FOOD-NASGOR", "name": "Nasi Goreng", "group": "Food", "rate": 35000, "station": "Hot Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-MIEGOR", "name": "Mie Goreng", "group": "Food", "rate": 35000, "station": "Hot Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-FRIES", "name": "French Fries", "group": "Food", "rate": 20000, "station": "Hot Kitchen", "prep": 10, "course": "Starter"},
    {"code": "FOOD-CIRENG", "name": "Cireng Bumbu Rujak", "group": "Food", "rate": 17000, "station": "Hot Kitchen", "prep": 10, "course": "Starter"},
    {"code": "FOOD-ROTI-COK", "name": "Roti Bakar Cokelat", "group": "Food", "rate": 15000, "station": "Hot Kitchen", "prep": 10, "course": "Dessert"},
    {"code": "FOOD-ROTI-KEJU", "name": "Roti Bakar Keju", "group": "Food", "rate": 15000, "station": "Hot Kitchen", "prep": 10, "course": "Dessert"},
    {"code": "FOOD-JAGUNG-MANIS", "name": "Jagung Bakar Manis", "group": "Food", "rate": 12000, "station": "Hot Kitchen", "prep": 12, "course": "Starter"},
    {"code": "FOOD-JAGUNG-PEDAS", "name": "Jagung Bakar Pedas", "group": "Food", "rate": 12000, "station": "Hot Kitchen", "prep": 12, "course": "Starter"},
    {"code": "FOOD-JAGUNG-MENTEGA", "name": "Jagung Bakar Mentega", "group": "Food", "rate": 12000, "station": "Hot Kitchen", "prep": 12, "course": "Starter"},
    {"code": "FOOD-DONAT", "name": "Donat Gula", "group": "Food", "rate": 8000, "station": "Pastry / Snack", "prep": 5, "course": "Dessert"},

    # Dimsum
    {"code": "DIM-UDANG-KEJU", "name": "Udang Keju (3)", "group": "Dimsum", "rate": 18000, "station": "Dimsum Station", "prep": 12, "course": "Starter"},
    {"code": "DIM-DRUMSTICK", "name": "Drumstick (3)", "group": "Dimsum", "rate": 18000, "station": "Dimsum Station", "prep": 12, "course": "Starter"},
    {"code": "DIM-UDANG-RAMBUTAN", "name": "Udang Rambutan (3)", "group": "Dimsum", "rate": 18000, "station": "Dimsum Station", "prep": 12, "course": "Starter"},
    {"code": "DIM-SIOMAY-AYAM", "name": "Siomay Ayam (3)", "group": "Dimsum", "rate": 15000, "station": "Dimsum Station", "prep": 10, "course": "Starter"},
    {"code": "DIM-SIOMAY-MOZZA", "name": "Siomay Mozza (3)", "group": "Dimsum", "rate": 15000, "station": "Dimsum Station", "prep": 10, "course": "Starter"},
    {"code": "DIM-GYOZA", "name": "Gyoza (3)", "group": "Dimsum", "rate": 15000, "station": "Dimsum Station", "prep": 12, "course": "Starter"},

    # Coffee (Black)
    {"code": "COF-ESPRESSO-HOT", "name": "Espresso Hot", "group": "Coffee", "rate": 18000, "station": "Bar / Beverage", "prep": 5, "course": "Beverage"},
    {"code": "COF-AMERICANO-HOT", "name": "Americano Hot", "group": "Coffee", "rate": 18000, "station": "Bar / Beverage", "prep": 5, "course": "Beverage"},
    {"code": "COF-AMERICANO-ICE", "name": "Americano Ice", "group": "Coffee", "rate": 20000, "station": "Bar / Beverage", "prep": 5, "course": "Beverage"},
    {"code": "COF-LONGBLCK-HOT", "name": "Longblack Hot", "group": "Coffee", "rate": 25000, "station": "Bar / Beverage", "prep": 5, "course": "Beverage"},
    {"code": "COF-LONGBLCK-ICE", "name": "Longblack Ice", "group": "Coffee", "rate": 27000, "station": "Bar / Beverage", "prep": 5, "course": "Beverage"},
    {"code": "COF-SIGNATURE-HOT", "name": "Signature Hot", "group": "Coffee", "rate": 25000, "station": "Bar / Beverage", "prep": 7, "course": "Beverage"},
    {"code": "COF-SIGNATURE-ICE", "name": "Signature Ice", "group": "Coffee", "rate": 28000, "station": "Bar / Beverage", "prep": 7, "course": "Beverage"},

    # Coffee (White)
    {"code": "COF-AREN-HOT", "name": "RR Gula Aren Hot", "group": "Coffee", "rate": 23000, "station": "Bar / Beverage", "prep": 5, "course": "Beverage"},
    {"code": "COF-AREN-ICE", "name": "RR Gula Aren Ice", "group": "Coffee", "rate": 25000, "station": "Bar / Beverage", "prep": 5, "course": "Beverage"},
    {"code": "COF-CAPPUCCINO-HOT", "name": "Cappuccino Hot", "group": "Coffee", "rate": 25000, "station": "Bar / Beverage", "prep": 7, "course": "Beverage"},
    {"code": "COF-CAPPUCCINO-ICE", "name": "Cappuccino Ice", "group": "Coffee", "rate": 27000, "station": "Bar / Beverage", "prep": 7, "course": "Beverage"},
    {"code": "COF-LATTE-HOT", "name": "Latte Hot", "group": "Coffee", "rate": 23000, "station": "Bar / Beverage", "prep": 7, "course": "Beverage"},
    {"code": "COF-LATTE-ICE", "name": "Latte Ice", "group": "Coffee", "rate": 25000, "station": "Bar / Beverage", "prep": 7, "course": "Beverage"},
    {"code": "COF-CARAMEL-HOT", "name": "Caramel Latte Hot", "group": "Coffee", "rate": 25000, "station": "Bar / Beverage", "prep": 7, "course": "Beverage"},
    {"code": "COF-CARAMEL-ICE", "name": "Caramel Latte Ice", "group": "Coffee", "rate": 27000, "station": "Bar / Beverage", "prep": 7, "course": "Beverage"},

    # Non-Coffee
    {"code": "NON-CHOCOLATE-HOT", "name": "Chocolate Hot", "group": "Non-Coffee", "rate": 23000, "station": "Bar / Beverage", "prep": 5, "course": "Beverage"},
    {"code": "NON-CHOCOLATE-ICE", "name": "Chocolate Ice", "group": "Non-Coffee", "rate": 25000, "station": "Bar / Beverage", "prep": 5, "course": "Beverage"},
    {"code": "NON-TEA-HOT", "name": "Tea Hot", "group": "Non-Coffee", "rate": 15000, "station": "Bar / Beverage", "prep": 5, "course": "Beverage"},
    {"code": "NON-TEA-ICE", "name": "Tea Ice", "group": "Non-Coffee", "rate": 17000, "station": "Bar / Beverage", "prep": 5, "course": "Beverage"},
    {"code": "NON-MILKTEA-HOT", "name": "Milk Tea Hot", "group": "Non-Coffee", "rate": 17000, "station": "Bar / Beverage", "prep": 5, "course": "Beverage"},
    {"code": "NON-MILKTEA-ICE", "name": "Milk Tea Ice", "group": "Non-Coffee", "rate": 19000, "station": "Bar / Beverage", "prep": 5, "course": "Beverage"},
    {"code": "NON-MATCHA-HOT", "name": "Matcha Latte Hot", "group": "Non-Coffee", "rate": 23000, "station": "Bar / Beverage", "prep": 5, "course": "Beverage"},
    {"code": "NON-MATCHA-ICE", "name": "Matcha Latte Ice", "group": "Non-Coffee", "rate": 25000, "station": "Bar / Beverage", "prep": 5, "course": "Beverage"},

    # Smoothies & Milkshake
    {"code": "SMO-MANGO", "name": "Tropical Mango", "group": "Beverage", "rate": 28000, "station": "Bar / Beverage", "prep": 8, "course": "Beverage"},
    {"code": "SMO-BERRY", "name": "Berry Blast", "group": "Beverage", "rate": 30000, "station": "Bar / Beverage", "prep": 8, "course": "Beverage"},
    {"code": "MILK-CHOCO", "name": "Choco Rindu", "group": "Beverage", "rate": 28000, "station": "Bar / Beverage", "prep": 8, "course": "Beverage"},
    {"code": "MILK-BANANA", "name": "Banana Caramel", "group": "Beverage", "rate": 30000, "station": "Bar / Beverage", "prep": 8, "course": "Beverage"},
]

KENARI_MENU = [
    {"code": "FOOD-KEN-NASGOR-SPESIAL", "name": "Nasi Goreng Spesial", "group": "Food", "rate": 38000, "station": "Main Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-KEN-NASGOR-SEAFOOD", "name": "Nasi Goreng Seafood", "group": "Food", "rate": 28000, "station": "Main Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-KEN-NASGOR-SPENCER", "name": "Nasi Goreng Spencer", "group": "Food", "rate": 30000, "station": "Main Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-KEN-NASGOR-SOSIS", "name": "Nasi Goreng Sosis", "group": "Food", "rate": 28000, "station": "Main Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-KEN-BAKMIE-GOR", "name": "Bakmie Goreng", "group": "Food", "rate": 28000, "station": "Main Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-KEN-KWETIAW-GOR", "name": "Kwetiaw Goreng", "group": "Food", "rate": 30000, "station": "Main Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-KEN-BIHUN-GOR", "name": "Bihun Goreng", "group": "Food", "rate": 30000, "station": "Main Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-KEN-DORI-BBQ", "name": "Dori Schnitzel BBQ", "group": "Food", "rate": 43000, "station": "Main Kitchen", "prep": 20, "course": "Main"},
    {"code": "FOOD-KEN-DORI-BLKPEP", "name": "Dori Schnitzel Blackpepper", "group": "Food", "rate": 43000, "station": "Main Kitchen", "prep": 20, "course": "Main"},
    {"code": "FOOD-KEN-DORI-THAI", "name": "Dori Crispy Sc Thai", "group": "Food", "rate": 40000, "station": "Main Kitchen", "prep": 20, "course": "Main"},
    {"code": "FOOD-KEN-GARLIC-CHICKEN", "name": "Garlic Chicken", "group": "Food", "rate": 35000, "station": "Main Kitchen", "prep": 20, "course": "Main"},
    {"code": "FOOD-KEN-AYAM-PANGGANG", "name": "Ayam Panggang Ketumbar", "group": "Food", "rate": 35000, "station": "Main Kitchen", "prep": 20, "course": "Main"},
    {"code": "FOOD-KEN-CHICKEN-STEAK", "name": "Crispy Chicken Steak", "group": "Food", "rate": 40000, "station": "Main Kitchen", "prep": 20, "course": "Main"},
    {"code": "FOOD-KEN-SUP-IGA", "name": "Soup Iga", "group": "Food", "rate": 43000, "station": "Main Kitchen", "prep": 20, "course": "Main"},
    {"code": "FOOD-KEN-SOTO-AYAM", "name": "Soto Ayam Spesial", "group": "Food", "rate": 30000, "station": "Main Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-KEN-BOWL-BLKPEP", "name": "Chicken Blackpepper", "group": "Food", "rate": 33000, "station": "Main Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-KEN-BOWL-MATAH", "name": "Chicken Sambal Matah", "group": "Food", "rate": 33000, "station": "Main Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-KEN-CHICKEN-SANDWICH", "name": "Chicken Sandwich", "group": "Food", "rate": 30000, "station": "Main Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-KEN-BEEF-SANDWICH", "name": "Fried Smoked Beef Sandwich", "group": "Food", "rate": 35000, "station": "Main Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-KEN-CHICKEN-BURGER", "name": "Chicken Burger", "group": "Food", "rate": 40000, "station": "Main Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-KEN-CAPCAY-GOR", "name": "Capcay Goreng", "group": "Food", "rate": 30000, "station": "Main Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-KEN-CAPCAY-KUAH", "name": "Capcay Kuah", "group": "Food", "rate": 30000, "station": "Main Kitchen", "prep": 15, "course": "Main"},
    {"code": "FOOD-KEN-FRIES", "name": "French Fries Kenari", "group": "Food", "rate": 20000, "station": "Main Kitchen", "prep": 10, "course": "Starter"},
    {"code": "FOOD-KEN-ONION-RING", "name": "Onion Ring", "group": "Food", "rate": 20000, "station": "Main Kitchen", "prep": 10, "course": "Starter"},
    {"code": "FOOD-KEN-LUMPIA-SAYUR", "name": "Lumpia Sayur", "group": "Food", "rate": 23000, "station": "Main Kitchen", "prep": 10, "course": "Starter"},
    {"code": "FOOD-KEN-BITTERBALLEN", "name": "Bitterballen", "group": "Food", "rate": 23000, "station": "Main Kitchen", "prep": 10, "course": "Starter"},
    {"code": "FOOD-KEN-MENDOAN", "name": "Tempe Mendoan", "group": "Food", "rate": 18000, "station": "Main Kitchen", "prep": 10, "course": "Starter"},
    {"code": "FOOD-KEN-MIX-PLATTER", "name": "Mix Platter", "group": "Food", "rate": 28000, "station": "Main Kitchen", "prep": 15, "course": "Starter"},
    {"code": "FOOD-KEN-PISANG-GORENG", "name": "Pisang Goreng Coklat Keju", "group": "Food", "rate": 23000, "station": "Main Kitchen", "prep": 10, "course": "Dessert"},
    {"code": "FOOD-KEN-TAPE-GORENG", "name": "Tape Goreng Susu Keju", "group": "Food", "rate": 23000, "station": "Main Kitchen", "prep": 10, "course": "Dessert"},
    {"code": "FOOD-KEN-FISH-FRIES", "name": "Fish & Fries", "group": "Food", "rate": 28000, "station": "Main Kitchen", "prep": 15, "course": "Starter"},
    {"code": "FOOD-KEN-CIRENG-AYAM", "name": "Cireng Ayam", "group": "Food", "rate": 18000, "station": "Main Kitchen", "prep": 10, "course": "Starter"},
    {"code": "FOOD-KEN-PANGSIT-GORENG", "name": "Pangsit Goreng", "group": "Food", "rate": 23000, "station": "Main Kitchen", "prep": 10, "course": "Starter"},
    {"code": "FOOD-KEN-NASI-PUTIH", "name": "Nasi Putih", "group": "Food", "rate": 10000, "station": "Main Kitchen", "prep": 5, "course": "Main"},
    {"code": "FOOD-KEN-TELUR-CEPLOK", "name": "Telur Ceplok", "group": "Food", "rate": 10000, "station": "Main Kitchen", "prep": 5, "course": "Starter"},
    {"code": "FOOD-KEN-TELUR-REBUS", "name": "Telur Rebus", "group": "Food", "rate": 20000, "station": "Main Kitchen", "prep": 5, "course": "Starter"},
    {"code": "FOOD-KEN-OMELETTE", "name": "Omelette", "group": "Food", "rate": 20000, "station": "Main Kitchen", "prep": 10, "course": "Starter"},
    {"code": "FOOD-KEN-TELUR-MATA-SAPI", "name": "Telur Mata Sapi", "group": "Food", "rate": 20000, "station": "Main Kitchen", "prep": 5, "course": "Starter"},
    {"code": "FOOD-KEN-SLICED-FRUIT", "name": "Sliced Fruit", "group": "Food", "rate": 20000, "station": "Main Kitchen", "prep": 5, "course": "Dessert"},
]


def _ensure_property_and_company(property_name: str = "Spencer Green Hotel", company: str | None = None) -> tuple[str, str]:
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
    company_name = company or prop.company or frappe.db.get_default("company")
    if not company_name:
        all_comps = frappe.get_all("Company", pluck="name", limit=1)
        company_name = all_comps[0] if all_comps else ""
    return property_name, company_name


@frappe.whitelist()
def setup_pos_profiles_and_cashier(
    property_name: str = "Spencer Green Hotel",
    company: str | None = None,
    cashier_username: str = "augustinussent@gmail.com",
) -> dict:
    """Setup default Customer, Bank/Cash payment accounts, POS Profiles, Cashier roles, and link Outlets."""
    # 0. Ensure Contact custom fields required by ERPNext party lookup
    if not frappe.db.exists("Custom Field", {"dt": "Contact", "fieldname": "is_billing_contact"}):
        try:
            cf = frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "Contact",
                "fieldname": "is_billing_contact",
                "label": "Is Billing Contact",
                "fieldtype": "Check",
                "insert_after": "is_primary_contact",
                "default": "0"
            })
            cf.flags.ignore_permissions = True
            cf.insert()
        except Exception:
            pass

    property_name, company_name = _ensure_property_and_company(property_name, company)

    # 1. Bank Account if missing
    bank_acc = frappe.db.get_value("Account", {"account_name": "Bank Operasional", "company": company_name}, "name")
    if not bank_acc:
        b_doc = frappe.get_doc({
            "doctype": "Account",
            "account_name": "Bank Operasional",
            "account_number": "1120.001",
            "parent_account": "1120.000 - Bank - SGH" if frappe.db.exists("Account", "1120.000 - Bank - SGH") else None,
            "company": company_name,
            "root_type": "Asset",
            "account_type": "Bank",
            "currency": "IDR",
            "is_group": 0,
        })
        b_doc.flags.ignore_permissions = True
        b_doc.insert()
        bank_acc = b_doc.name

    # 2. Mode of Payment Accounts
    if frappe.db.exists("Mode of Payment", "Cash"):
        m_cash = frappe.get_doc("Mode of Payment", "Cash")
        m_cash.accounts = [a for a in m_cash.accounts if a.company != company_name]
        m_cash.append("accounts", {"company": company_name, "default_account": "1111.001 - Kas Kecil - SGH"})
        m_cash.flags.ignore_permissions = True
        m_cash.save()

    if frappe.db.exists("Mode of Payment", "Credit Card") and bank_acc:
        m_cc = frappe.get_doc("Mode of Payment", "Credit Card")
        m_cc.accounts = [a for a in m_cc.accounts if a.company != company_name]
        m_cc.append("accounts", {"company": company_name, "default_account": bank_acc})
        m_cc.flags.ignore_permissions = True
        m_cc.save()

    # 3. Default Customer
    cust_name = "Walk-in Customer"
    if not frappe.db.exists("Customer", cust_name):
        c_doc = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": cust_name,
            "customer_group": "Commercial" if frappe.db.exists("Customer Group", "Commercial") else "All Customer Groups",
            "territory": "Indonesia" if frappe.db.exists("Territory", "Indonesia") else "All Territories",
            "customer_type": "Individual",
        })
        c_doc.flags.ignore_permissions = True
        c_doc.insert()

    # 4. Cashier Roles
    roles_to_add = ["Restaurant Cashier", "Restaurant Captain", "Hotel Manager", "Cashier", "Sales User", "Accounts User"]
    if frappe.db.exists("User", cashier_username):
        for r in roles_to_add:
            if frappe.db.exists("Role", r) and not frappe.db.exists("Has Role", {"parent": cashier_username, "role": r}):
                frappe.get_doc({
                    "doctype": "Has Role",
                    "parent": cashier_username,
                    "parentfield": "roles",
                    "parenttype": "User",
                    "role": r
                }).insert(ignore_permissions=True)
        frappe.clear_cache(user=cashier_username)

    # 5. POS Profile: Rintik Rindu
    pos_rr_name = "POS-Rintik-Rindu"
    if frappe.db.exists("POS Profile", pos_rr_name):
        frappe.delete_doc("POS Profile", pos_rr_name, force=1)

    pos_rr = frappe.get_doc({
        "doctype": "POS Profile",
        "name": pos_rr_name,
        "company": company_name,
        "warehouse": "Stores - SGH" if frappe.db.exists("Warehouse", "Stores - SGH") else None,
        "customer": cust_name,
        "selling_price_list": "Standard Selling",
        "currency": "IDR",
        "income_account": "4110.000 - Penjualan - SGH",
        "expense_account": "5110.020 - Penyesuaian Stock - SGH" if frappe.db.exists("Account", "5110.020 - Penyesuaian Stock - SGH") else None,
        "write_off_account": "5510.009 - Selisih Pembayaran Customer - SGH" if frappe.db.exists("Account", "5510.009 - Selisih Pembayaran Customer - SGH") else "4110.000 - Penjualan - SGH",
        "write_off_cost_center": "Main - SGH",
        "cost_center": "Main - SGH",
        "allow_discount_change": 1,
        "allow_rate_change": 0,
        "applicable_for_users": [{"user": cashier_username, "default": 1}],
        "payments": [
            {"mode_of_payment": "Cash", "default": 1},
            {"mode_of_payment": "Credit Card", "default": 0}
        ]
    })
    pos_rr.flags.ignore_permissions = True
    pos_rr.insert()

    # Link Outlet Rintik Rindu
    if frappe.db.exists("Hotel Outlet", "Rintik Rindu Pool Cafe"):
        outlet_rr = frappe.get_doc("Hotel Outlet", "Rintik Rindu Pool Cafe")
        outlet_rr.pos_profile = pos_rr_name
        outlet_rr.warehouse = "Stores - SGH"
        outlet_rr.cost_center = "Main - SGH"
        outlet_rr.income_account = "4110.000 - Penjualan - SGH"
        outlet_rr.default_customer = cust_name
        outlet_rr.default_mode_of_payment = "Cash"
        outlet_rr.selling_price_list = "Standard Selling"
        outlet_rr.require_pos_opening_entry = 0
        outlet_rr.flags.ignore_permissions = True
        outlet_rr.save()

    # 6. POS Profile: Kenari Restaurant
    pos_kn_name = "POS-Kenari-Restaurant"
    if frappe.db.exists("POS Profile", pos_kn_name):
        frappe.delete_doc("POS Profile", pos_kn_name, force=1)

    pos_kn = frappe.get_doc({
        "doctype": "POS Profile",
        "name": pos_kn_name,
        "company": company_name,
        "warehouse": "Stores - SGH" if frappe.db.exists("Warehouse", "Stores - SGH") else None,
        "customer": cust_name,
        "selling_price_list": "Standard Selling",
        "currency": "IDR",
        "income_account": "4110.000 - Penjualan - SGH",
        "expense_account": "5110.020 - Penyesuaian Stock - SGH" if frappe.db.exists("Account", "5110.020 - Penyesuaian Stock - SGH") else None,
        "write_off_account": "5510.009 - Selisih Pembayaran Customer - SGH" if frappe.db.exists("Account", "5510.009 - Selisih Pembayaran Customer - SGH") else "4110.000 - Penjualan - SGH",
        "write_off_cost_center": "Main - SGH",
        "cost_center": "Main - SGH",
        "allow_discount_change": 1,
        "allow_rate_change": 0,
        "applicable_for_users": [{"user": cashier_username, "default": 0}],
        "payments": [
            {"mode_of_payment": "Cash", "default": 1},
            {"mode_of_payment": "Credit Card", "default": 0}
        ]
    })
    pos_kn.flags.ignore_permissions = True
    pos_kn.insert()

    if frappe.db.exists("Hotel Outlet", "Kenari Restaurant"):
        outlet_kn = frappe.get_doc("Hotel Outlet", "Kenari Restaurant")
        outlet_kn.pos_profile = pos_kn_name
        outlet_kn.warehouse = "Stores - SGH"
        outlet_kn.cost_center = "Main - SGH"
        outlet_kn.income_account = "4110.000 - Penjualan - SGH"
        outlet_kn.default_customer = cust_name
        outlet_kn.default_mode_of_payment = "Cash"
        outlet_kn.selling_price_list = "Standard Selling"
        outlet_kn.require_pos_opening_entry = 0
        outlet_kn.flags.ignore_permissions = True
        outlet_kn.save()

    return {
        "status": "success",
        "cashier": cashier_username,
        "pos_profiles": [pos_rr_name, pos_kn_name],
        "default_customer": cust_name,
    }


@frappe.whitelist()
def seed_rintik_rindu_pos(property_name: str = "Spencer Green Hotel", company: str | None = None, cashier_username: str = "augustinussent@gmail.com") -> dict:
    """Idempotently seed Rintik Rindu Pool Cafe outlet, stations, tables, items, and menu items."""
    property_name, company_name = _ensure_property_and_company(property_name, company)

    # Outlet
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

    # Kitchen Production Units
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

    # Dining Area
    area_name = "Poolside Area"
    dining_area_id = f"{outlet_name}-{area_name}"
    if not frappe.db.exists("Hotel Dining Area", dining_area_id):
        a_doc = frappe.get_doc({
            "doctype": "Hotel Dining Area",
            "outlet": outlet_name,
            "area_name": area_name,
            "display_order": 1,
            "enabled": 1,
        })
        a_doc.flags.ignore_permissions = True
        a_doc.insert()

    # Tables
    for t_idx in range(1, 11):
        t_name = f"RR-{t_idx:02d}"
        table_id = f"{outlet_name}-{t_name}"
        if not frappe.db.exists("Hotel Restaurant Table", table_id):
            t_doc = frappe.get_doc({
                "doctype": "Hotel Restaurant Table",
                "outlet": outlet_name,
                "dining_area": dining_area_id,
                "table_name": t_name,
                "seats": 4,
                "status": "Available",
                "enabled": 1,
            })
            t_doc.flags.ignore_permissions = True
            t_doc.insert()

    # Item Groups & Items
    created_items = 0
    created_menu_items = 0
    for item_spec in RINTIK_RINDU_MENU:
        if not frappe.db.exists("Item Group", item_spec["group"]):
            try:
                ig_doc = frappe.get_doc({
                    "doctype": "Item Group",
                    "item_group_name": item_spec["group"],
                    "is_group": 0,
                    "parent_item_group": "All Item Groups" if frappe.db.exists("Item Group", "All Item Groups") else "",
                })
                ig_doc.flags.ignore_permissions = True
                ig_doc.insert()
            except Exception:
                pass

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
                "course": item_spec.get("course", "Main"),
                "available": 1,
                "allow_qr_ordering": 1,
            })
            m_doc.flags.ignore_permissions = True
            m_doc.insert()
            created_menu_items += 1

    pos_info = setup_pos_profiles_and_cashier(property_name, company_name, cashier_username)

    return {
        "status": "success",
        "outlet": outlet_name,
        "total_items_in_catalog": len(RINTIK_RINDU_MENU),
        "created_items": created_items,
        "created_menu_items": created_menu_items,
        "tables_created": 10,
        "pos_setup": pos_info,
    }


@frappe.whitelist()
def seed_kenari_restaurant_pos(property_name: str = "Spencer Green Hotel", company: str | None = None, cashier_username: str = "augustinussent@gmail.com") -> dict:
    """Idempotently seed Kenari Restaurant outlet, tables, items, and menu items."""
    property_name, company_name = _ensure_property_and_company(property_name, company)

    outlet_name = "Kenari Restaurant"
    if not frappe.db.exists("Hotel Outlet", outlet_name):
        outlet_doc = frappe.get_doc({
            "doctype": "Hotel Outlet",
            "outlet_name": outlet_name,
            "property": property_name,
            "company": company_name,
            "outlet_type": "Restaurant",
            "enabled": 1,
            "allow_room_posting": 1,
            "allow_qr_ordering": 1,
            "public_slug": "kenari-restaurant",
            "inventory_posting_policy": "ERPNext POS Finished Goods",
            "require_pos_opening_entry": 0,
            "cashier_discount_limit": 10,
        })
        outlet_doc.flags.ignore_permissions = True
        outlet_doc.insert()

    # Main Kitchen Unit
    unit_name = frappe.db.get_value("Hotel Kitchen Production Unit", {"outlet": outlet_name, "unit_name": "Main Kitchen"}, "name")
    if not unit_name:
        u_doc = frappe.get_doc({
            "doctype": "Hotel Kitchen Production Unit",
            "property": property_name,
            "outlet": outlet_name,
            "unit_name": "Main Kitchen",
            "warning_minutes": 15,
            "critical_minutes": 25,
        })
        u_doc.flags.ignore_permissions = True
        u_doc.insert()
        unit_name = u_doc.name

    # Dining Area
    area_name = "Main Dining Room"
    dining_area_id = f"{outlet_name}-{area_name}"
    if not frappe.db.exists("Hotel Dining Area", dining_area_id):
        a_doc = frappe.get_doc({
            "doctype": "Hotel Dining Area",
            "outlet": outlet_name,
            "area_name": area_name,
            "display_order": 1,
            "enabled": 1,
        })
        a_doc.flags.ignore_permissions = True
        a_doc.insert()

    # Tables
    for t_idx in range(1, 16):
        t_name = f"KN-{t_idx:02d}"
        table_id = f"{outlet_name}-{t_name}"
        if not frappe.db.exists("Hotel Restaurant Table", table_id):
            t_doc = frappe.get_doc({
                "doctype": "Hotel Restaurant Table",
                "outlet": outlet_name,
                "dining_area": dining_area_id,
                "table_name": t_name,
                "seats": 4,
                "status": "Available",
                "enabled": 1,
            })
            t_doc.flags.ignore_permissions = True
            t_doc.insert()

    created_items = 0
    created_menu_items = 0
    for item_spec in KENARI_MENU:
        if not frappe.db.exists("Item Group", item_spec["group"]):
            try:
                ig_doc = frappe.get_doc({
                    "doctype": "Item Group",
                    "item_group_name": item_spec["group"],
                    "is_group": 0,
                    "parent_item_group": "All Item Groups" if frappe.db.exists("Item Group", "All Item Groups") else "",
                })
                ig_doc.flags.ignore_permissions = True
                ig_doc.insert()
            except Exception:
                pass

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
                "production_unit": unit_name,
                "preparation_minutes": item_spec["prep"],
                "course": item_spec.get("course", "Main"),
                "available": 1,
                "allow_qr_ordering": 1,
            })
            m_doc.flags.ignore_permissions = True
            m_doc.insert()
            created_menu_items += 1

    return {
        "status": "success",
        "outlet": outlet_name,
        "total_items_in_catalog": len(KENARI_MENU),
        "created_items": created_items,
        "created_menu_items": created_menu_items,
        "tables_created": 15,
    }


@frappe.whitelist()
def seed_all_outlets_pos(property_name: str = "Spencer Green Hotel", company: str | None = None, cashier_username: str = "augustinussent@gmail.com") -> dict:
    """Seed both Rintik Rindu Pool Cafe and Kenari Restaurant with POS profiles."""
    rr = seed_rintik_rindu_pos(property_name, company, cashier_username)
    kn = seed_kenari_restaurant_pos(property_name, company, cashier_username)
    pos_info = setup_pos_profiles_and_cashier(property_name, company, cashier_username)
    return {
        "rintik_rindu": rr,
        "kenari_restaurant": kn,
        "pos_setup": pos_info,
    }
