from __future__ import annotations

import frappe


def on_submit(doc, method=None) -> None:
    """Mirror a submitted POS Invoice into the folio for visibility only.

    Revenue and stock are already booked by POS Invoice, so mirrored rows are
    marked `is_already_invoiced` and excluded from the checkout Sales Invoice.
    """
    folio_name = getattr(doc, "custom_hotel_folio", None)
    if not getattr(doc, "custom_post_to_hotel_folio", 0) or not folio_name:
        return
    if not frappe.db.exists("Hotel Folio", folio_name):
        frappe.throw(f"Hotel Folio {folio_name} does not exist")

    folio = frappe.get_doc("Hotel Folio", folio_name)
    for item in doc.items:
        key = f"POS:{doc.name}:{item.idx}"
        if frappe.db.exists("Hotel Folio Charge", {"parent": folio.name, "idempotency_key": key}):
            continue
        folio.append(
            "charges",
            {
                "posting_date": doc.posting_date,
                "charge_type": "Food & Beverage",
                "item_code": item.item_code,
                "description": item.description or item.item_name,
                "qty": item.qty,
                "rate": item.rate,
                "cost_center": item.cost_center,
                "source_doctype": "POS Invoice",
                "source_name": doc.name,
                "idempotency_key": key,
                "is_already_invoiced": 1,
            },
        )
    folio.save(ignore_permissions=True)


def on_cancel(doc, method=None) -> None:
    folio_name = getattr(doc, "custom_hotel_folio", None)
    if not folio_name or not frappe.db.exists("Hotel Folio", folio_name):
        return
    rows = frappe.get_all(
        "Hotel Folio Charge",
        filters={"parent": folio_name, "source_doctype": "POS Invoice", "source_name": doc.name},
        pluck="name",
    )
    for row_name in rows:
        frappe.db.set_value("Hotel Folio Charge", row_name, {"is_void": 1, "void_reason": "Source POS Invoice cancelled"})
