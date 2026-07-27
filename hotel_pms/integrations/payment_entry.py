
import frappe
from hotel_pms.front_desk import on_payment_entry_change as on_reservation_payment_change
from hotel_pms.billing import on_payment_entry_change as on_cashier_payment_change

def infer_reservation_from_references(doc):
    if getattr(doc,"custom_hotel_reservation",None): return
    for row in getattr(doc,"references",[]) or []:
        if row.reference_doctype in ("Sales Order","Sales Invoice") and frappe.get_meta(row.reference_doctype).has_field("custom_hotel_reservation"):
            reservation=frappe.db.get_value(row.reference_doctype,row.reference_name,"custom_hotel_reservation")
            if reservation:
                doc.db_set("custom_hotel_reservation",reservation,update_modified=False); doc.custom_hotel_reservation=reservation; return

def on_submit(doc, method=None):
    from hotel_pms.webhooks import emit_document_event
    emit_document_event(doc, method or "on_submit")
    infer_reservation_from_references(doc)
    on_reservation_payment_change(doc, method)
    on_cashier_payment_change(doc, method)

def on_cancel(doc, method=None):
    from hotel_pms.webhooks import emit_document_event
    emit_document_event(doc, method or "on_cancel")
    infer_reservation_from_references(doc)
    on_reservation_payment_change(doc, method)
    on_cashier_payment_change(doc, method)
