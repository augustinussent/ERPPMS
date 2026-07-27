from __future__ import annotations

import frappe


def on_submit(doc, method=None) -> None:
    folio = getattr(doc, "custom_hotel_folio", None)
    if folio and frappe.db.exists("Hotel Folio", folio):
        frappe.db.set_value("Hotel Folio", folio, {"status": "Invoiced", "sales_invoice": doc.name})


def on_cancel(doc, method=None) -> None:
    folio = getattr(doc, "custom_hotel_folio", None)
    if folio and frappe.db.exists("Hotel Folio", folio):
        frappe.db.set_value("Hotel Folio", folio, {"status": "Open", "sales_invoice": None})
