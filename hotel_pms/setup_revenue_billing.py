from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ROLES = ["Revenue Manager", "Cashier", "Credit Manager"]


def setup_revenue_billing() -> None:
    for role_name in ROLES:
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert(ignore_permissions=True)
    create_custom_fields(
        {
            "Payment Entry": [
                {
                    "fieldname": "custom_hotel_cashier_shift",
                    "label": "Hotel Cashier Shift",
                    "fieldtype": "Link",
                    "options": "Hotel Cashier Shift",
                    "insert_after": "custom_hotel_transaction_type",
                    "no_copy": 1,
                },
            ],
            "POS Invoice": [
                {
                    "fieldname": "custom_hotel_cashier_shift",
                    "label": "Hotel Cashier Shift",
                    "fieldtype": "Link",
                    "options": "Hotel Cashier Shift",
                    "insert_after": "custom_hotel_folio",
                    "no_copy": 1,
                },
            ],
            "Payment Request": [
                {
                    "fieldname": "custom_hotel_sync_key",
                    "label": "Hotel PMS Sync Key",
                    "fieldtype": "Data",
                    "insert_after": "reference_name",
                    "read_only": 1,
                    "hidden": 1,
                    "unique": 1,
                    "no_copy": 1,
                },
            ],
            "Purchase Invoice": [
                {
                    "fieldname": "custom_hotel_sync_key",
                    "label": "Hotel PMS Sync Key",
                    "fieldtype": "Data",
                    "insert_after": "supplier",
                    "read_only": 1,
                    "hidden": 1,
                    "unique": 1,
                    "no_copy": 1,
                },
                {
                    "fieldname": "custom_hotel_travel_agent_settlement",
                    "label": "Hotel Travel Agent Settlement",
                    "fieldtype": "Link",
                    "options": "Hotel Travel Agent Settlement",
                    "insert_after": "custom_hotel_sync_key",
                    "read_only": 1,
                    "no_copy": 1,
                },
            ],
            "Sales Invoice": [
                {
                    "fieldname": "custom_hotel_city_ledger_folio",
                    "label": "Hotel City Ledger Folio",
                    "fieldtype": "Link",
                    "options": "Hotel City Ledger Folio",
                    "insert_after": "custom_hotel_group_folio",
                    "read_only": 1,
                    "no_copy": 1,
                },
                {
                    "fieldname": "custom_hotel_tax_profile",
                    "label": "Hotel Tax Profile",
                    "fieldtype": "Link",
                    "options": "Hotel Tax Profile",
                    "insert_after": "custom_hotel_city_ledger_folio",
                    "read_only": 1,
                    "no_copy": 1,
                },
            ],
        },
        update=True,
    )
    _add_indexes()


def _add_indexes() -> None:
    indexes = {
        "Hotel Rate Calendar": [["property", "rate_date", "room_type", "rate_plan"]],
        "Hotel Voucher Redemption": [["voucher", "customer", "status"]],
        "Hotel Cashier Shift": [["property", "cashier", "status"]],
        "Hotel Folio Transfer": [["source_folio", "destination_folio", "status"]],
        "Hotel Travel Agent Settlement": [["contract", "period_from", "period_to"]],
    }
    for doctype, groups in indexes.items():
        if not frappe.db.exists("DocType", doctype):
            continue
        for fields in groups:
            try:
                frappe.db.add_index(doctype, fields)
            except Exception:
                pass
