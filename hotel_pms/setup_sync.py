from __future__ import annotations

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def setup_sync_fields() -> None:
    fields = {}
    for doctype, insert_after in {
        "Project": "project_name",
        "Quotation": "party_name",
        "Sales Order": "customer",
        "Sales Invoice": "customer",
        "Payment Entry": "party_name",
    }.items():
        fields[doctype] = [
            {
                "fieldname": "custom_hotel_sync_key",
                "label": "Hotel PMS Sync Key",
                "fieldtype": "Data",
                "insert_after": insert_after,
                "read_only": 1,
                "hidden": 1,
                "unique": 1,
                "no_copy": 1,
            }
        ]
    create_custom_fields(fields, update=True)
