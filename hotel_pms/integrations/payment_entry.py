from hotel_pms.front_desk import on_payment_entry_change as on_reservation_payment_change
from hotel_pms.billing import on_payment_entry_change as on_cashier_payment_change


def on_submit(doc, method=None):
    on_reservation_payment_change(doc, method)
    on_cashier_payment_change(doc, method)


def on_cancel(doc, method=None):
    on_reservation_payment_change(doc, method)
    on_cashier_payment_change(doc, method)
