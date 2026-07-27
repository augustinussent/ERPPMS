from __future__ import annotations

import json
from decimal import Decimal

import frappe
from frappe import _
from frappe.exceptions import DuplicateEntryError
from frappe.utils import add_days, cint, flt, getdate, now_datetime, nowdate

from hotel_pms.revenue_rules import conserve_split, money
from hotel_pms.sync import create_document_once, make_sync_key
from hotel_pms.localization.registry import resolve_invoice_tax_context

FOLIO_CONFIG = {
    "Hotel Folio": {"charge_doctype": "Hotel Folio Charge", "category_field": "charge_type"},
    "Hotel Group Folio": {"charge_doctype": "Hotel Group Folio Charge", "category_field": "charge_category"},
    "Hotel City Ledger Folio": {"charge_doctype": "Hotel City Ledger Charge", "category_field": "charge_category"},
}


def _require_billing_user() -> None:
    frappe.only_for(["System Manager", "Hotel Manager", "Front Desk", "Night Auditor", "Accounts User", "Accounts Manager", "Cashier", "Credit Manager"])


def _json(payload) -> dict:
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            frappe.throw(_("Invalid JSON payload: {0}").format(exc))
    return payload or {}


def _folio_doc(doctype: str, name: str):
    if doctype not in FOLIO_CONFIG:
        frappe.throw(_("Unsupported folio type: {0}").format(doctype))
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("write")
    return doc


def _charge_payload(row, category_field: str, *, amount: Decimal, key: str, transfer_source: str | None = None) -> dict:
    qty = Decimal("1")
    payload = {
        "posting_date": row.posting_date,
        category_field: row.get("charge_type") or row.get("charge_category") or "Other",
        "item_code": row.item_code,
        "description": row.description,
        "qty": float(qty),
        "rate": float(money(amount)),
        "cost_center": row.cost_center,
        "source_doctype": "Hotel Folio Transfer",
        "source_name": transfer_source,
        "idempotency_key": key,
    }
    if category_field == "charge_type" and row.get("room"):
        payload["room"] = row.room
    if category_field == "charge_category":
        if row.get("billing_destination"):
            payload["billing_destination"] = row.billing_destination
        if row.get("billing_customer"):
            payload["billing_customer"] = row.billing_customer
        if row.get("participant_name"):
            payload["participant_name"] = row.participant_name
    if transfer_source and "transfer_source" in [f.fieldname for f in row.meta.fields]:
        payload["transfer_source"] = transfer_source
    return payload


def _find_charge(parent_doc, row_name: str):
    return next((row for row in parent_doc.charges if row.name == row_name), None)


@frappe.whitelist()
def transfer_folio_charges(payload) -> dict:
    _require_billing_user()
    data = _json(payload)
    required = ["source_folio_type", "source_folio", "destination_folio_type", "destination_folio", "lines", "reason", "request_key"]
    for field in required:
        if not data.get(field):
            frappe.throw(_("Missing required field: {0}").format(field))
    if data["source_folio_type"] == data["destination_folio_type"] and data["source_folio"] == data["destination_folio"]:
        frappe.throw(_("Source and destination folio must be different."))
    key = make_sync_key("FOLIOTR", data["source_folio_type"], data["source_folio"], data["destination_folio_type"], data["destination_folio"], data["request_key"])
    existing = frappe.db.get_value("Hotel Folio Transfer", {"idempotency_key": key}, "name")
    if existing:
        return {"transfer": existing, "already_processed": True}

    source = _folio_doc(data["source_folio_type"], data["source_folio"])
    destination = _folio_doc(data["destination_folio_type"], data["destination_folio"])
    if source.property != destination.property:
        frappe.throw(_("Cross-property folio transfer is not allowed."))
    frappe.db.sql(f"select name from `tab{source.doctype}` where name=%s for update", source.name)
    frappe.db.sql(f"select name from `tab{destination.doctype}` where name=%s for update", destination.name)
    source.reload(); destination.reload()

    transfer = frappe.get_doc({
        "doctype": "Hotel Folio Transfer", "property": source.property,
        "source_folio_type": source.doctype, "source_folio": source.name,
        "destination_folio_type": destination.doctype, "destination_folio": destination.name,
        "transfer_type": "Split" if any(flt(row.get("percentage")) or flt(row.get("amount")) for row in data["lines"]) else "Transfer",
        "reason": data["reason"], "idempotency_key": key,
    })
    transfer.insert(ignore_permissions=True)
    src_cat = FOLIO_CONFIG[source.doctype]["category_field"]
    dst_cat = FOLIO_CONFIG[destination.doctype]["category_field"]

    for index, request in enumerate(data["lines"], start=1):
        row = _find_charge(source, request.get("source_charge_row"))
        if not row:
            frappe.throw(_("Source charge row {0} was not found.").format(request.get("source_charge_row")))
        if row.is_void or row.is_already_invoiced or row.sales_invoice:
            frappe.throw(_("Charge {0} is void or already invoiced and cannot be transferred.").format(row.name))
        original = money(row.amount)
        percentage = Decimal(str(request.get("percentage") or 0))
        transfer_amount = money(original * percentage / Decimal("100")) if percentage else money(request.get("amount") or original)
        if transfer_amount <= 0 or transfer_amount > original:
            frappe.throw(_("Transfer amount for row {0} must be greater than zero and not exceed the original amount.").format(row.name))
        remainder = money(original - transfer_amount)
        if not conserve_split(original, transfer_amount, remainder):
            frappe.throw(_("Transfer conservation failed for charge {0}.").format(row.name))

        row.is_void = 1
        row.void_reason = f"Transferred by {transfer.name}: {data['reason']}"
        remainder_row = None
        if remainder > 0:
            remainder_row = source.append("charges", _charge_payload(
                row, src_cat, amount=remainder, key=f"{key}:SRC:{index}", transfer_source=transfer.name
            ))
        dest_row = destination.append("charges", _charge_payload(
            row, dst_cat, amount=transfer_amount, key=f"{key}:DST:{index}", transfer_source=transfer.name
        ))
        transfer.append("lines", {
            "source_charge_row": row.name, "item_code": row.item_code, "description": row.description,
            "original_amount": float(original), "transfer_amount": float(transfer_amount),
            "transfer_percentage": float(percentage),
        })
        source.save(ignore_permissions=True)
        destination.save(ignore_permissions=True)
        line = transfer.lines[-1]
        line.source_remainder_row = remainder_row.name if remainder_row else None
        line.destination_charge_row = dest_row.name

    transfer.status = "Applied"
    transfer.save(ignore_permissions=True)
    transfer.submit()
    return {"transfer": transfer.name, "already_processed": False, "total_transferred": transfer.total_transferred}


@frappe.whitelist()
def reverse_folio_transfer(transfer_name: str, reason: str, request_key: str) -> dict:
    _require_billing_user()
    if not reason:
        frappe.throw(_("A reversal reason is required."))
    original = frappe.get_doc("Hotel Folio Transfer", transfer_name)
    original.check_permission("write")
    if original.docstatus != 1 or original.status != "Applied" or original.reversed_by:
        frappe.throw(_("Only an applied, unreversed transfer can be reversed."))
    key = make_sync_key("FOLIOREV", original.name, request_key)
    existing = frappe.db.get_value("Hotel Folio Transfer", {"idempotency_key": key}, "name")
    if existing:
        return {"transfer": existing, "already_processed": True}
    source = _folio_doc(original.source_folio_type, original.source_folio)
    destination = _folio_doc(original.destination_folio_type, original.destination_folio)
    source.reload(); destination.reload()
    reversal = frappe.get_doc({
        "doctype": "Hotel Folio Transfer", "property": original.property,
        "source_folio_type": original.destination_folio_type, "source_folio": original.destination_folio,
        "destination_folio_type": original.source_folio_type, "destination_folio": original.source_folio,
        "transfer_type": "Reversal", "reason": reason, "reverses_transfer": original.name,
        "idempotency_key": key,
    })
    reversal.insert(ignore_permissions=True)
    for line in original.lines:
        source_original = _find_charge(source, line.source_charge_row)
        dest_generated = _find_charge(destination, line.destination_charge_row)
        remainder_generated = _find_charge(source, line.source_remainder_row) if line.source_remainder_row else None
        if not source_original or not dest_generated:
            frappe.throw(_("Transfer audit rows are incomplete; reversal stopped."))
        for generated in [dest_generated, remainder_generated]:
            if generated and (generated.is_already_invoiced or generated.sales_invoice or generated.is_void):
                frappe.throw(_("Generated charge {0} has been invoiced, voided, or further changed; reverse downstream actions first.").format(generated.name))
        dest_generated.is_void = 1
        dest_generated.void_reason = f"Reversed by {reversal.name}: {reason}"
        if remainder_generated:
            remainder_generated.is_void = 1
            remainder_generated.void_reason = f"Reversed by {reversal.name}: {reason}"
        source_original.is_void = 0
        source_original.void_reason = None
        reversal.append("lines", {
            "source_charge_row": dest_generated.name, "item_code": line.item_code, "description": line.description,
            "original_amount": line.transfer_amount, "transfer_amount": line.transfer_amount,
            "destination_charge_row": source_original.name,
        })
    source.save(ignore_permissions=True); destination.save(ignore_permissions=True)
    reversal.status = "Applied"; reversal.save(ignore_permissions=True); reversal.submit()
    original.db_set({"status": "Reversed", "reversed_by": reversal.name})
    return {"transfer": reversal.name, "already_processed": False}


@frappe.whitelist()
def request_direct_bill_approval(reservation: str, city_ledger_account: str, amount: float, reason: str, request_key: str) -> dict:
    _require_billing_user()
    account = frappe.get_doc("Hotel City Ledger Account", city_ledger_account)
    if account.status != "Active":
        frappe.throw(_("City ledger account is not active."))
    reservation_doc = frappe.get_doc("Hotel Reservation", reservation)
    if reservation_doc.property != account.property:
        frappe.throw(_("Reservation and city ledger account belong to different properties."))
    key = make_sync_key("DIRECTBILL", reservation, city_ledger_account, request_key)
    existing = frappe.db.get_value("Hotel Direct Bill Approval", {"idempotency_key": key}, "name")
    if existing:
        return {"approval": existing, "already_created": True}
    doc = frappe.get_doc({
        "doctype": "Hotel Direct Bill Approval", "reservation": reservation,
        "city_ledger_account": city_ledger_account, "requested_amount": amount,
        "reason": reason, "idempotency_key": key,
    })
    doc.insert()
    return {"approval": doc.name, "already_created": False}


@frappe.whitelist()
def approve_direct_bill(approval: str, approved_amount: float | None = None) -> dict:
    frappe.only_for(["System Manager", "Hotel Manager", "Credit Manager", "Accounts Manager"])
    doc = frappe.get_doc("Hotel Direct Bill Approval", approval)
    doc.check_permission("write")
    account = frappe.get_doc("Hotel City Ledger Account", doc.city_ledger_account)
    amount = flt(approved_amount or doc.requested_amount)
    current_exposure = flt(
        frappe.db.sql(
            """
            select coalesce(sum(outstanding_amount), 0)
            from `tabSales Invoice`
            where customer=%s and company=%s and docstatus=1 and outstanding_amount > 0
            """,
            (account.customer, frappe.db.get_value("Hotel Property", account.property, "company")),
        )[0][0]
    )
    if account.credit_limit and current_exposure + amount > flt(account.credit_limit):
        frappe.throw(
            _("Approval would exceed the hotel credit limit. Current exposure: {0}; requested: {1}; limit: {2}.").format(
                current_exposure, amount, account.credit_limit
            )
        )
    doc.db_set({"approved_amount": amount, "status": "Approved", "approved_by": frappe.session.user, "approved_at": now_datetime()})
    frappe.db.set_value("Hotel Reservation", doc.reservation, {"direct_bill_approval": doc.name, "billing_route": "Direct Bill"})
    return {"approval": doc.name, "status": "Approved", "approved_amount": amount}


def _active_invoice_rows(folio_doc) -> list:
    return [row for row in folio_doc.charges if not row.is_void and not row.is_already_invoiced and not row.sales_invoice]


@frappe.whitelist()
def create_city_ledger_sales_invoice(folio: str) -> dict:
    frappe.only_for(["System Manager", "Hotel Manager", "Accounts User", "Accounts Manager", "Credit Manager"])
    doc = frappe.get_doc("Hotel City Ledger Folio", folio)
    doc.check_permission("write")
    charges = _active_invoice_rows(doc)
    if not charges:
        frappe.throw(_("No uninvoiced city-ledger charges are available."))
    account = frappe.get_doc("Hotel City Ledger Account", doc.city_ledger_account)
    property_doc = frappe.get_doc("Hotel Property", doc.property)
    key = make_sync_key("SI", "CITYLEDGER", doc.name, *sorted(row.name for row in charges))

    def build():
        invoice = frappe.new_doc("Sales Invoice")
        invoice.company = property_doc.company
        invoice.customer = account.customer
        invoice.posting_date = getdate()
        if invoice.meta.has_field("allocate_advances_automatically"):
            invoice.allocate_advances_automatically = True
        if account.payment_terms_template:
            invoice.payment_terms_template = account.payment_terms_template
        if invoice.meta.has_field("custom_hotel_city_ledger_folio"):
            invoice.custom_hotel_city_ledger_folio = doc.name
        tax_context = resolve_invoice_tax_context(doc.property, [charge.tax_profile for charge in charges])
        if invoice.meta.has_field("custom_hotel_tax_profile"):
            invoice.custom_hotel_tax_profile = tax_context["tax_profile"]
        if tax_context["sales_taxes_template"]:
            invoice.taxes_and_charges = tax_context["sales_taxes_template"]
            invoice.set_taxes()
        for charge in charges:
            invoice.append("items", {
                "item_code": charge.item_code, "description": charge.description,
                "qty": charge.qty, "rate": charge.rate,
                "cost_center": charge.cost_center or property_doc.default_cost_center,
            })
        return invoice

    invoice, already = create_document_once(
        base_key=key, operation="Create City Ledger Sales Invoice",
        source_doctype=doc.doctype, source_name=doc.name, target_doctype="Sales Invoice",
        build_document=build, payload={"folio": doc.name, "charges": [r.name for r in charges]},
    )
    for row in charges:
        row.sales_invoice = invoice.name
    doc.sales_invoice = invoice.name; doc.status = "Invoiced"; doc.save(ignore_permissions=True)
    return {"sales_invoice": invoice.name, "already_created": already}


def _property_tax_template(property_doc) -> str | None:
    profile_name = property_doc.default_hotel_tax_profile
    if profile_name:
        template = frappe.db.get_value("Hotel Tax Profile", profile_name, "sales_taxes_template")
        if template:
            return template
    return property_doc.default_sales_taxes_template


@frappe.whitelist()
def get_checkout_summary(reservation: str) -> dict:
    _require_billing_user()
    reservation_doc = frappe.get_doc("Hotel Reservation", reservation)
    reservation_doc.check_permission("read")
    folio_name = reservation_doc.folio or frappe.db.get_value("Hotel Folio", {"reservation": reservation}, "name")
    folio = frappe.get_doc("Hotel Folio", folio_name) if folio_name else None
    charges = []
    if folio:
        for row in folio.charges:
            charges.append({
                "row": row.name, "posting_date": str(row.posting_date), "type": row.charge_type,
                "description": row.description, "amount": flt(row.amount), "is_void": cint(row.is_void),
                "sales_invoice": row.sales_invoice,
            })
    invoices = []
    invoice_names = sorted({row["sales_invoice"] for row in charges if row.get("sales_invoice")})
    for name in invoice_names:
        if frappe.db.exists("Sales Invoice", name):
            invoices.append(frappe.db.get_value("Sales Invoice", name, ["name", "docstatus", "grand_total", "outstanding_amount"], as_dict=True))
    from hotel_pms.front_desk import get_deposit_summary
    deposit = get_deposit_summary(reservation)
    direct = frappe.db.get_value("Hotel Direct Bill Approval", {"reservation": reservation}, ["name", "status", "approved_amount", "city_ledger_account"], as_dict=True)
    payment_requests = []
    if invoice_names:
        payment_requests = frappe.get_all(
            "Payment Request",
            filters={"reference_doctype": "Sales Invoice", "reference_name": ("in", invoice_names), "docstatus": ("<", 2)},
            fields=["name", "reference_name", "status", "grand_total", "outstanding_amount", "payment_url"],
        )
    active_total = sum(Decimal(str(row["amount"])) for row in charges if not row["is_void"])
    uninvoiced = sum(Decimal(str(row["amount"])) for row in charges if not row["is_void"] and not row["sales_invoice"])
    outstanding = sum(Decimal(str(row.outstanding_amount or 0)) for row in invoices if row.docstatus != 2)
    return {
        "reservation": reservation_doc.as_dict(), "folio": folio_name, "charges": charges, "invoices": invoices,
        "payment_requests": payment_requests, "deposit": deposit, "direct_bill_approval": direct,
        "totals": {"active_charges": float(money(active_total)), "uninvoiced": float(money(uninvoiced)),
                   "invoice_outstanding": float(money(outstanding)),
                   "net_due_after_available_deposit": float(max(money(uninvoiced + outstanding - Decimal(str(deposit.get('available_credit') or 0))), Decimal('0')))},
    }


@frappe.whitelist()
def create_payment_request_for_invoice(
    sales_invoice: str,
    recipient_email: str | None = None,
    payment_gateway_account: str | None = None,
    submit: int = 0,
) -> dict:
    _require_billing_user()
    invoice = frappe.get_doc("Sales Invoice", sales_invoice)
    invoice.check_permission("read")
    if invoice.docstatus != 1 or flt(invoice.outstanding_amount) <= 0:
        frappe.throw(_("Submit an invoice with an outstanding balance before creating a payment request."))
    key = make_sync_key("PAYREQ", invoice.name, payment_gateway_account or "DEFAULT")
    existing = frappe.db.get_value("Payment Request", {"custom_hotel_sync_key": key, "docstatus": ("<", 2)}, "name")
    if existing:
        return {"payment_request": existing, "already_created": True, "payment_url": frappe.db.get_value("Payment Request", existing, "payment_url")}
    from erpnext.accounts.doctype.payment_request.payment_request import make_payment_request
    pr = make_payment_request(
        dt="Sales Invoice", dn=invoice.name, recipient_id=recipient_email or invoice.contact_email or invoice.owner,
        payment_gateway_account=payment_gateway_account, submit_doc=0, return_doc=1, mute_email=1,
        party_type="Customer", party=invoice.customer, party_name=invoice.customer_name,
        mode_of_payment=None, make_sales_invoice=0,
    )
    if isinstance(pr, dict):
        pr = frappe.get_doc(pr)
    if pr.get("__unsaved"):
        pr.insert(ignore_permissions=True)
    pr.db_set("custom_hotel_sync_key", key)
    if cint(submit) and pr.docstatus == 0:
        pr.flags.mute_email = True
        pr.submit()
    if not frappe.db.exists("Hotel ERP Sync Log", key):
        frappe.get_doc({
            "doctype": "Hotel ERP Sync Log", "idempotency_key": key, "status": "Completed",
            "operation": "Create Hotel Payment Request", "source_doctype": "Sales Invoice", "source_name": invoice.name,
            "target_doctype": "Payment Request", "target_name": pr.name, "completed_at": now_datetime(),
        }).insert(ignore_permissions=True)
    return {"payment_request": pr.name, "already_created": False, "payment_url": pr.payment_url}


@frappe.whitelist()
def open_cashier_shift(property: str, mode_of_payment: str, opening_float: float = 0, request_key: str | None = None) -> dict:
    frappe.only_for(["System Manager", "Hotel Manager", "Cashier", "Accounts Manager"])
    existing = frappe.db.get_value("Hotel Cashier Shift", {"property": property, "cashier": frappe.session.user, "status": ("in", ["Open", "Closing Review"])}, "name")
    if existing:
        return {"cashier_shift": existing, "already_open": True}
    property_doc = frappe.get_doc("Hotel Property", property)
    account = frappe.db.get_value("Mode of Payment Account", {"parent": mode_of_payment, "company": property_doc.company}, "default_account")
    if not account:
        frappe.throw(_("Mode of Payment {0} has no default account for company {1}.").format(mode_of_payment, property_doc.company))
    key = make_sync_key("CASHSHIFT", property, frappe.session.user, request_key or now_datetime())
    doc = frappe.get_doc({
        "doctype": "Hotel Cashier Shift", "property": property, "company": property_doc.company,
        "cashier": frappe.session.user, "mode_of_payment": mode_of_payment, "cash_account": account,
        "opening_float": opening_float, "idempotency_key": key,
    })
    doc.insert()
    return {"cashier_shift": doc.name, "already_open": False}


def recalculate_cashier_shift(shift_name: str) -> dict:
    shift = frappe.get_doc("Hotel Cashier Shift", shift_name)
    receipts = refunds = Decimal("0")
    entries = frappe.get_all(
        "Payment Entry",
        filters={"custom_hotel_cashier_shift": shift.name, "docstatus": 1},
        fields=["payment_type", "paid_from", "paid_to", "paid_amount", "received_amount"],
    )
    for row in entries:
        if row.payment_type == "Receive" and row.paid_to == shift.cash_account:
            receipts += Decimal(str(row.received_amount or 0))
        elif row.payment_type == "Pay" and row.paid_from == shift.cash_account:
            refunds += Decimal(str(row.paid_amount or 0))
    if frappe.get_meta("POS Invoice").has_field("custom_hotel_cashier_shift"):
        pos_rows = frappe.db.sql(
            """
            select coalesce(sum(p.amount), 0) as amount
            from `tabPOS Invoice` pi
            inner join `tabSales Invoice Payment` p on p.parent=pi.name and p.parenttype='POS Invoice'
            where pi.custom_hotel_cashier_shift=%s and pi.docstatus=1 and p.account=%s
            """,
            (shift.name, shift.cash_account), as_dict=True,
        )
        pos_amount = Decimal(str(pos_rows[0].amount or 0)) if pos_rows else Decimal("0")
        if pos_amount >= 0:
            receipts += pos_amount
        else:
            refunds += abs(pos_amount)
    movements = frappe.get_all("Hotel Cashier Movement", filters={"cashier_shift": shift.name, "docstatus": 1}, fields=["movement_type", "amount"])
    adjustment = Decimal("0")
    for row in movements:
        sign = Decimal("1") if row.movement_type in ("Float In", "Correction In") else Decimal("-1")
        adjustment += sign * Decimal(str(row.amount or 0))
    expected = money(Decimal(str(shift.opening_float or 0)) + receipts - refunds + adjustment)
    values = {"cash_receipts": float(money(receipts)), "cash_refunds": float(money(refunds)), "drawer_adjustments": float(money(adjustment)), "expected_cash": float(expected)}
    if shift.counted_cash is not None:
        values["variance"] = float(money(Decimal(str(shift.counted_cash or 0)) - expected))
    frappe.db.set_value("Hotel Cashier Shift", shift.name, values)
    return values


@frappe.whitelist()
def get_cashier_shift_summary(shift: str) -> dict:
    _require_billing_user()
    doc = frappe.get_doc("Hotel Cashier Shift", shift)
    doc.check_permission("read")
    totals = recalculate_cashier_shift(shift)
    entries = frappe.get_all(
        "Payment Entry", filters={"custom_hotel_cashier_shift": shift, "docstatus": ("<", 2)},
        fields=["name", "posting_date", "payment_type", "party", "paid_amount", "received_amount", "docstatus"], order_by="creation asc",
    )
    movements = frappe.get_all("Hotel Cashier Movement", filters={"cashier_shift": shift, "docstatus": ("<", 2)}, fields=["name", "movement_at", "movement_type", "amount", "reason", "docstatus"], order_by="movement_at asc")
    return {"shift": doc.as_dict(), "totals": totals, "payment_entries": entries, "movements": movements}


@frappe.whitelist()
def record_cashier_movement(shift: str, movement_type: str, amount: float, reason: str, request_key: str) -> dict:
    frappe.only_for(["System Manager", "Hotel Manager", "Cashier", "Accounts Manager"])
    doc = frappe.get_doc("Hotel Cashier Shift", shift)
    if doc.status != "Open":
        frappe.throw(_("Cashier shift is not open."))
    if doc.cashier != frappe.session.user and not ({"System Manager", "Hotel Manager", "Accounts Manager"} & set(frappe.get_roles())):
        frappe.throw(_("Only the assigned cashier or a manager can record drawer movements."))
    key = make_sync_key("CASHMOVE", shift, request_key)
    existing = frappe.db.get_value("Hotel Cashier Movement", {"idempotency_key": key}, "name")
    if existing:
        return {"movement": existing, "already_created": True}
    movement = frappe.get_doc({
        "doctype": "Hotel Cashier Movement", "cashier_shift": shift, "movement_type": movement_type,
        "amount": amount, "reason": reason, "approved_by": frappe.session.user, "idempotency_key": key,
    })
    movement.insert(); movement.submit(); recalculate_cashier_shift(shift)
    return {"movement": movement.name, "already_created": False}


@frappe.whitelist()
def close_cashier_shift(shift: str, counted_cash: float, variance_reason: str | None = None) -> dict:
    frappe.only_for(["System Manager", "Hotel Manager", "Cashier", "Accounts Manager"])
    doc = frappe.get_doc("Hotel Cashier Shift", shift)
    doc.check_permission("write")
    if doc.status not in ("Open", "Closing Review"):
        frappe.throw(_("Only an open or closing-review shift can be closed."))
    doc.counted_cash = counted_cash
    doc.save()
    totals = recalculate_cashier_shift(shift)
    doc.reload()
    if flt(doc.variance) and not variance_reason:
        frappe.throw(_("Variance reason is required when counted cash differs from expected cash."))
    roles = set(frappe.get_roles())
    threshold = flt(frappe.db.get_single_value("Hotel PMS Settings", "cashier_variance_approval_threshold") or 0)
    requires_manager = threshold > 0 and abs(flt(doc.variance)) > threshold
    is_manager = bool({"System Manager", "Hotel Manager", "Accounts Manager"} & roles)
    if requires_manager and not is_manager:
        doc.db_set({
            "variance_reason": variance_reason,
            "status": "Closing Review",
            "closed_at": None,
            "closed_by": None,
        })
        return {
            "cashier_shift": doc.name,
            "status": "Closing Review",
            "requires_manager_approval": True,
            **totals,
            "counted_cash": counted_cash,
            "variance": doc.variance,
        }
    doc.db_set({"variance_reason": variance_reason, "status": "Closed", "closed_at": now_datetime(), "closed_by": frappe.session.user})
    return {"cashier_shift": doc.name, "status": "Closed", "requires_manager_approval": False, **totals, "counted_cash": counted_cash, "variance": doc.variance}


def on_payment_entry_change(doc, method=None) -> None:
    shift = getattr(doc, "custom_hotel_cashier_shift", None)
    if shift and frappe.db.exists("Hotel Cashier Shift", shift):
        recalculate_cashier_shift(shift)
