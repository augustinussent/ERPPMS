from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from hotel_pms.setup_group_booking import setup_group_booking
from hotel_pms.setup_sync import setup_sync_fields


ROLES = ["Hotel Manager", "Front Desk", "Night Auditor", "Housekeeping", "Engineering", "Hotel Sales", "Banquet"]


def before_install() -> None:
    for role_name in ROLES:
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert(ignore_permissions=True)


def after_install() -> None:
    create_custom_fields(
        {
            "Sales Invoice": [
                {
                    "fieldname": "custom_hotel_reservation",
                    "label": "Hotel Reservation",
                    "fieldtype": "Link",
                    "options": "Hotel Reservation",
                    "insert_after": "customer",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_hotel_folio",
                    "label": "Hotel Folio",
                    "fieldtype": "Link",
                    "options": "Hotel Folio",
                    "insert_after": "custom_hotel_reservation",
                    "read_only": 1,
                },
            ],
            "POS Invoice": [
                {
                    "fieldname": "custom_post_to_hotel_folio",
                    "label": "Post to Hotel Folio",
                    "fieldtype": "Check",
                    "insert_after": "customer",
                },
                {
                    "fieldname": "custom_hotel_folio",
                    "label": "Hotel Folio",
                    "fieldtype": "Link",
                    "options": "Hotel Folio",
                    "insert_after": "custom_post_to_hotel_folio",
                    "depends_on": "eval:doc.custom_post_to_hotel_folio",
                },
            ],
        },
        update=True,
    )
    setup_group_booking()
    setup_sync_fields()
