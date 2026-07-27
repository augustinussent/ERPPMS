from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from hotel_pms.setup_group_booking import setup_group_booking
from hotel_pms.setup_sync import setup_sync_fields
from hotel_pms.setup_front_office import setup_front_office
from hotel_pms.setup_operations import setup_operations
from hotel_pms.setup_revenue_billing import setup_revenue_billing
from hotel_pms.setup_guest_facing import setup_guest_facing
from hotel_pms.setup_services import setup_services
from hotel_pms.setup_platform import setup_platform
from hotel_pms.setup_production_gate import setup_production_gate
from hotel_pms.setup_adoption import setup_adoption


ROLES = ["Hotel Manager", "Front Desk", "Night Auditor", "Housekeeping", "Housekeeping Supervisor", "Engineering", "Engineering Supervisor", "Hotel Sales", "Banquet", "Revenue Manager", "Cashier", "Credit Manager", "Restaurant Cashier", "Restaurant Captain", "Kitchen", "Laundry", "Guest Services", "Hotel API User", "Hotel Cross Property Manager"]


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
    setup_front_office()
    setup_operations()
    setup_revenue_billing()
    setup_guest_facing()
    setup_services()
    setup_platform()
    setup_production_gate()
    setup_adoption()
