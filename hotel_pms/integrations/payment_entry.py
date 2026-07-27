from hotel_pms.front_desk import on_payment_entry_change


def on_submit(doc, method=None):
    on_payment_entry_change(doc, method)


def on_cancel(doc, method=None):
    on_payment_entry_change(doc, method)
