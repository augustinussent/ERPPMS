import frappe

from hotel_pms.setup_front_office import setup_front_office
from hotel_pms.setup_sync import setup_sync_fields


def execute():
    setup_sync_fields()
    setup_front_office()
    if frappe.db.has_column("Hotel Reservation", "deposit_amount") and frappe.db.has_column("Hotel Reservation", "required_deposit"):
        frappe.db.sql(
            """
            update `tabHotel Reservation`
            set required_deposit = deposit_amount
            where coalesce(required_deposit, 0) = 0 and coalesce(deposit_amount, 0) > 0
            """
        )
