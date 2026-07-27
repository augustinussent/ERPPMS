from __future__ import annotations

import frappe


def on_submit(doc, method=None) -> None:
    folio = getattr(doc, "custom_hotel_folio", None)
    if folio and frappe.db.exists("Hotel Folio", folio):
        rows = frappe.get_all(
            "Hotel Folio Charge",
            filters={"parent": folio, "sales_invoice": doc.name},
            pluck="name",
        )
        for row_name in rows:
            frappe.db.set_value(
                "Hotel Folio Charge",
                row_name,
                "is_already_invoiced",
                1,
                update_modified=False,
            )
        frappe.db.set_value("Hotel Folio", folio, {"status": "Invoiced", "sales_invoice": doc.name})

    group_folio = getattr(doc, "custom_hotel_group_folio", None)
    if group_folio and frappe.db.exists("Hotel Group Folio", group_folio):
        rows = frappe.get_all(
            "Hotel Group Folio Charge",
            filters={"parent": group_folio, "sales_invoice": doc.name},
            pluck="name",
        )
        for row_name in rows:
            frappe.db.set_value(
                "Hotel Group Folio Charge",
                row_name,
                "is_already_invoiced",
                1,
                update_modified=False,
            )
        frappe.db.set_value("Hotel Group Folio", group_folio, "status", "Invoiced")


def on_cancel(doc, method=None) -> None:
    folio = getattr(doc, "custom_hotel_folio", None)
    if folio and frappe.db.exists("Hotel Folio", folio):
        rows = frappe.get_all(
            "Hotel Folio Charge",
            filters={"parent": folio, "sales_invoice": doc.name},
            pluck="name",
        )
        for row_name in rows:
            frappe.db.set_value(
                "Hotel Folio Charge",
                row_name,
                {"is_already_invoiced": 0, "sales_invoice": None},
                update_modified=False,
            )
        remaining = frappe.db.get_value(
            "Hotel Folio Charge",
            {"parent": folio, "sales_invoice": ("is", "set")},
            "sales_invoice",
        )
        frappe.db.set_value(
            "Hotel Folio",
            folio,
            {"status": "Invoiced" if remaining else "Open", "sales_invoice": remaining},
        )

    group_folio = getattr(doc, "custom_hotel_group_folio", None)
    if group_folio and frappe.db.exists("Hotel Group Folio", group_folio):
        rows = frappe.get_all(
            "Hotel Group Folio Charge",
            filters={"parent": group_folio, "sales_invoice": doc.name},
            pluck="name",
        )
        for row_name in rows:
            frappe.db.set_value(
                "Hotel Group Folio Charge",
                row_name,
                {"is_already_invoiced": 0, "sales_invoice": None},
                update_modified=False,
            )
        remaining = frappe.db.get_value(
            "Hotel Group Folio Charge",
            {"parent": group_folio, "sales_invoice": ("is", "set")},
            "sales_invoice",
        )
        frappe.db.set_value(
            "Hotel Group Folio",
            group_folio,
            {"status": "Invoiced" if remaining else "Open", "sales_invoice": remaining},
        )


def on_trash(doc, method=None) -> None:
    # Draft invoices can be deleted without an on_cancel event. Release their folio rows.
    on_cancel(doc, method)
