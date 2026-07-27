from __future__ import annotations

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import now_datetime

from hotel_pms.sync import make_sync_key


def _document_status(doctype: str, name: str | None) -> int | None:
    if not name or not frappe.db.exists(doctype, name):
        return None
    return frappe.db.get_value(doctype, name, "docstatus") or 0


def _active_doc(doctype: str, name: str | None) -> bool:
    status = _document_status(doctype, name)
    return status is not None and status != 2


def _reconcile_charge_invoice_links(charge_doctype: str, parent: str) -> tuple[list[str], int]:
    """Return active invoice names and repair per-row invoice flags."""
    active_invoices: list[str] = []
    repaired = 0
    rows = frappe.get_all(
        charge_doctype,
        filters={"parent": parent},
        fields=["name", "sales_invoice", "is_already_invoiced"],
        order_by="idx asc",
    )
    for row in rows:
        if not row.sales_invoice:
            continue
        invoice_status = _document_status("Sales Invoice", row.sales_invoice)
        if invoice_status is None or invoice_status == 2:
            frappe.db.set_value(
                charge_doctype,
                row.name,
                {"sales_invoice": None, "is_already_invoiced": 0},
                update_modified=False,
            )
            repaired += 1
            continue
        active_invoices.append(row.sales_invoice)
        expected_invoiced = 1 if invoice_status == 1 else 0
        if int(row.is_already_invoiced or 0) != expected_invoiced:
            frappe.db.set_value(
                charge_doctype,
                row.name,
                "is_already_invoiced",
                expected_invoiced,
                update_modified=False,
            )
            repaired += 1
    return active_invoices, repaired


def reconcile_erpnext_links() -> dict:
    """Repair derived links without creating accounting documents.

    This routine is deliberately conservative: it reconnects documents that already
    exist, but never invents a new invoice or order. Creation remains behind explicit,
    idempotent commands.
    """
    repaired = 0

    for row in frappe.get_all("Hotel Folio", fields=["name", "reservation", "sales_invoice", "status"]):
        active_invoices, row_repairs = _reconcile_charge_invoice_links("Hotel Folio Charge", row.name)
        repaired += row_repairs
        active_invoice = active_invoices[-1] if active_invoices else None
        expected_status = "Invoiced" if active_invoice else "Open"
        if row.status in ("Open", "Invoiced") and (row.sales_invoice != active_invoice or row.status != expected_status):
            frappe.db.set_value(
                "Hotel Folio",
                row.name,
                {"sales_invoice": active_invoice, "status": expected_status},
                update_modified=False,
            )
            repaired += 1
        if row.reservation:
            linked = frappe.db.get_value("Hotel Reservation", row.reservation, "folio")
            if linked != row.name:
                frappe.db.set_value("Hotel Reservation", row.reservation, "folio", row.name, update_modified=False)
                repaired += 1

    for row in frappe.get_all("Hotel Group Folio", fields=["name", "group_booking", "sales_invoice", "status"]):
        active_invoices, row_repairs = _reconcile_charge_invoice_links("Hotel Group Folio Charge", row.name)
        repaired += row_repairs
        active_invoice = active_invoices[-1] if active_invoices else None
        expected_status = "Invoiced" if active_invoice else "Open"
        if row.status in ("Open", "Invoiced") and (row.sales_invoice != active_invoice or row.status != expected_status):
            frappe.db.set_value(
                "Hotel Group Folio",
                row.name,
                {"sales_invoice": active_invoice, "status": expected_status},
                update_modified=False,
            )
            repaired += 1
        if row.group_booking:
            linked = frappe.db.get_value("Hotel Group Booking", row.group_booking, "group_folio")
            if linked != row.name:
                frappe.db.set_value("Hotel Group Booking", row.group_booking, "group_folio", row.name, update_modified=False)
                repaired += 1

    # Restore group commercial links from active ERPNext documents.
    for booking in frappe.get_all("Hotel Group Booking", fields=["name", "quotation", "sales_order", "project"]):
        mappings = [
            ("quotation", "Quotation", "custom_hotel_group_booking", make_sync_key("QTN", "GROUP", booking.name)),
            ("sales_order", "Sales Order", "custom_hotel_group_booking", make_sync_key("SO", "GROUP", booking.name)),
            ("project", "Project", None, make_sync_key("PROJECT", "GROUP", booking.name)),
        ]
        for source_field, target_doctype, link_field, sync_key in mappings:
            current = booking.get(source_field)
            if _active_doc(target_doctype, current):
                continue
            target = frappe.db.get_value(
                target_doctype,
                {"custom_hotel_sync_key": sync_key, "docstatus": ("!=", 2)},
                "name",
                order_by="creation desc",
            )
            if not target and link_field:
                target = frappe.db.get_value(
                    target_doctype,
                    {link_field: booking.name, "docstatus": ("!=", 2)},
                    "name",
                    order_by="creation desc",
                )
            if target and current != target:
                frappe.db.set_value("Hotel Group Booking", booking.name, source_field, target, update_modified=False)
                repaired += 1

    return {"repaired": repaired}


@frappe.whitelist()
def run_reconciliation() -> dict:
    frappe.only_for(["System Manager", "Hotel Manager"])
    return reconcile_erpnext_links()


@frappe.whitelist()
def get_sync_health() -> dict:
    frappe.only_for(["System Manager", "Hotel Manager"])
    stale_before = now_datetime() - timedelta(minutes=15)
    stale_logs = frappe.get_all(
        "Hotel ERP Sync Log",
        filters={"status": "In Progress", "creation": ("<", stale_before)},
        fields=["name", "operation", "source_doctype", "source_name", "creation"],
        order_by="creation asc",
    )
    broken_targets = []
    for log in frappe.get_all(
        "Hotel ERP Sync Log",
        filters={"status": "Completed"},
        fields=["name", "target_doctype", "target_name"],
    ):
        if not log.target_name or not frappe.db.exists(log.target_doctype, log.target_name):
            broken_targets.append(log.name)

    unlinked_folio_charges = frappe.db.sql(
        """
        select count(*)
        from `tabHotel Folio Charge`
        where is_already_invoiced = 1
          and coalesce(source_doctype, '') != 'POS Invoice'
          and coalesce(sales_invoice, '') = ''
        """
    )[0][0]
    unlinked_group_charges = frappe.db.sql(
        """
        select count(*)
        from `tabHotel Group Folio Charge`
        where is_already_invoiced = 1
          and coalesce(sales_invoice, '') = ''
        """
    )[0][0]
    healthy = not stale_logs and not broken_targets and not unlinked_folio_charges and not unlinked_group_charges
    return {
        "healthy": healthy,
        "stale_in_progress_logs": stale_logs,
        "broken_sync_targets": broken_targets,
        "invoiced_folio_rows_without_invoice": unlinked_folio_charges,
        "invoiced_group_rows_without_invoice": unlinked_group_charges,
        "message": _("No synchronization anomalies were found.")
        if healthy
        else _("Synchronization anomalies require administrator review."),
    }


def backfill_legacy_invoice_links() -> dict:
    """Link v0.2 folio rows to their existing header-level Sales Invoice."""
    updated = 0
    for folio in frappe.get_all("Hotel Folio", fields=["name", "sales_invoice"]):
        if not folio.sales_invoice or not frappe.db.exists("Sales Invoice", folio.sales_invoice):
            continue
        invoice_status = _document_status("Sales Invoice", folio.sales_invoice)
        invoice_creation = frappe.db.get_value("Sales Invoice", folio.sales_invoice, "creation")
        rows = frappe.get_all(
            "Hotel Folio Charge",
            filters={
                "parent": folio.name,
                "is_void": 0,
                "sales_invoice": ("is", "not set"),
                "creation": ("<=", invoice_creation),
            },
            fields=["name", "source_doctype"],
        )
        for row in rows:
            if row.source_doctype == "POS Invoice":
                continue
            frappe.db.set_value(
                "Hotel Folio Charge",
                row.name,
                {
                    "sales_invoice": folio.sales_invoice,
                    "is_already_invoiced": 1 if invoice_status == 1 else 0,
                },
                update_modified=False,
            )
            updated += 1
    return {"updated": updated}


def backfill_sync_keys() -> dict:
    """Add deterministic keys to ERPNext documents linked by v0.2 fields."""
    updated = 0
    for booking in frappe.get_all("Hotel Group Booking", fields=["name", "quotation", "sales_order", "project"]):
        targets = [
            ("Quotation", booking.quotation, make_sync_key("QTN", "GROUP", booking.name)),
            ("Sales Order", booking.sales_order, make_sync_key("SO", "GROUP", booking.name)),
            ("Project", booking.project, make_sync_key("PROJECT", "GROUP", booking.name)),
        ]
        for doctype, name, key in targets:
            if name and frappe.db.exists(doctype, name) and not frappe.db.get_value(doctype, name, "custom_hotel_sync_key"):
                frappe.db.set_value(doctype, name, "custom_hotel_sync_key", key, update_modified=False)
                updated += 1

    for folio in frappe.get_all("Hotel Folio", fields=["name", "sales_invoice"]):
        if folio.sales_invoice and frappe.db.exists("Sales Invoice", folio.sales_invoice):
            if not frappe.db.get_value("Sales Invoice", folio.sales_invoice, "custom_hotel_sync_key"):
                key = make_sync_key("SI", "FOLIO", folio.name, "LEGACY", folio.sales_invoice)
                frappe.db.set_value("Sales Invoice", folio.sales_invoice, "custom_hotel_sync_key", key, update_modified=False)
                updated += 1

    group_invoices = frappe.db.sql(
        """
        select distinct parent, sales_invoice
        from `tabHotel Group Folio Charge`
        where coalesce(sales_invoice, '') != ''
        """,
        as_dict=True,
    )
    for row in group_invoices:
        if frappe.db.exists("Sales Invoice", row.sales_invoice) and not frappe.db.get_value(
            "Sales Invoice", row.sales_invoice, "custom_hotel_sync_key"
        ):
            key = make_sync_key("SI", "GROUP-FOLIO", row.parent, "LEGACY", row.sales_invoice)
            frappe.db.set_value("Sales Invoice", row.sales_invoice, "custom_hotel_sync_key", key, update_modified=False)
            updated += 1
    return {"updated": updated}
