from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime, nowdate

from hotel_pms import __version__
from hotel_pms.intelligence_rules import ground_explanation, payment_correction_plan
from hotel_pms.platform import assigned_properties, is_privileged

INTELLIGENCE_ROLES = {"Hotel Manager", "Night Auditor", "Hotel Intelligence Analyst", "System Manager"}
FINANCE_ROLES = {"Hotel Manager", "Accounts Manager", "System Manager"}
FINANCE_ACCESS_ROLES = FINANCE_ROLES | {"Accounts User"}


def _require_intelligence_access(property_name: str | None = None) -> None:
    roles = set(frappe.get_roles())
    if not is_privileged() and not roles.intersection(INTELLIGENCE_ROLES):
        frappe.throw(_("Hotel intelligence access is required."), frappe.PermissionError)
    if property_name and not is_privileged() and property_name not in assigned_properties():
        frappe.throw(_("Not permitted for this property."), frappe.PermissionError)


def _require_finance_manager() -> None:
    if not is_privileged() and not set(frappe.get_roles()).intersection(FINANCE_ROLES):
        frappe.throw(_("Hotel Manager, Accounts Manager, or System Manager role required."), frappe.PermissionError)


def _require_finance_access(property_name: str | None = None) -> None:
    if not is_privileged() and not set(frappe.get_roles()).intersection(FINANCE_ACCESS_ROLES):
        frappe.throw(_("Accounts or hotel finance access is required."), frappe.PermissionError)
    if property_name and not is_privileged() and property_name not in assigned_properties():
        frappe.throw(_("Not permitted for this property."), frappe.PermissionError)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _config(property_name: str, agent_type: str):
    name = frappe.db.get_value("Hotel Intelligence Config", {"property": property_name, "agent_type": agent_type}, "name")
    if name:
        return frappe.get_doc("Hotel Intelligence Config", name)
    doc = frappe.get_doc({
        "doctype": "Hotel Intelligence Config",
        "property": property_name,
        "agent_type": agent_type,
        "enabled": 0,
        "mode": "Suggest",
        "confidence_threshold": 85,
        "autopilot_allowed": 0,
        "config_json": _json({"cash_variance_threshold": 1000, "stock_posting_grace_minutes": 20}),
    })
    doc.insert(ignore_permissions=True)
    return doc


def _new_run(property_name: str, agent_type: str, business_date, triggered_by: str):
    return frappe.get_doc({
        "doctype": "Hotel Intelligence Run",
        "property": property_name,
        "agent_type": agent_type,
        "business_date": business_date,
        "triggered_by": triggered_by,
        "status": "Running",
        "started_at": now_datetime(),
        "executed_by": frappe.session.user,
        "source_version": __version__,
    }).insert(ignore_permissions=True)


def _finish_run(run, status: str, signals: dict, summary: dict, error: str | None = None) -> None:
    completed = now_datetime()
    run.flags.intelligence_internal_update = True
    run.status = status
    run.completed_at = completed
    run.duration_seconds = max((completed - run.started_at).total_seconds(), 0)
    run.signals_json = _json(signals)
    run.summary_json = _json(summary)
    run.input_hash = _digest(signals)
    run.finding_count = int(summary.get("findings") or 0)
    run.decision_count = int(summary.get("decisions") or 0)
    run.error_message = error
    run.save(ignore_permissions=True)


def _finding_fingerprint(property_name: str, business_date, finding_type: str, reference_doctype: str, reference_name: str) -> str:
    return _digest([property_name, str(business_date), finding_type, reference_doctype, reference_name])


def _upsert_finding(run, data: dict) -> str:
    fingerprint = _finding_fingerprint(
        run.property, run.business_date, data["finding_type"], data.get("reference_doctype") or "", data.get("reference_name") or ""
    )
    now = now_datetime()
    existing = frappe.db.get_value("Hotel Night Audit Finding", {"fingerprint": fingerprint}, "name")
    values = {
        **data,
        "property": run.property,
        "business_date": run.business_date,
        "fingerprint": fingerprint,
        "intelligence_run": run.name,
        "last_seen_at": now,
        "evidence_json": _json(data.get("evidence") or {}),
    }
    values.pop("evidence", None)
    if existing:
        doc = frappe.get_doc("Hotel Night Audit Finding", existing)
        # False positives stay closed until an auditor explicitly reopens them.
        if doc.status == "Resolved":
            doc.status = "Open"
            doc.resolution_notes = None
            doc.resolved_by = None
        doc.update(values)
        doc.save(ignore_permissions=True)
        return doc.name
    values["first_seen_at"] = now
    values["status"] = "Open"
    return frappe.get_doc({"doctype": "Hotel Night Audit Finding", **values}).insert(ignore_permissions=True).name


def _folio_charge_summary(folio_names: list[str]) -> dict[str, dict]:
    if not folio_names:
        return {}
    rows = frappe.get_all(
        "Hotel Folio Charge",
        filters={"parent": ["in", folio_names], "parenttype": "Hotel Folio"},
        fields=["parent", "charge_type", "amount", "tax_profile", "sales_invoice"],
        limit_page_length=0,
    )
    result: dict[str, dict] = {}
    for row in rows:
        item = result.setdefault(row.parent, {"count": 0, "room_count": 0, "missing_tax": 0, "total": 0.0})
        item["count"] += 1
        item["total"] += flt(row.amount)
        if row.charge_type == "Room":
            item["room_count"] += 1
        if flt(row.amount) > 0 and row.charge_type not in ("Tax", "Adjustment") and not row.tax_profile:
            item["missing_tax"] += 1
    return result


def _collect_night_audit_findings(property_name: str, business_date, config: dict) -> tuple[list[dict], dict]:
    findings: list[dict] = []
    signals: dict[str, Any] = {}
    reservations = frappe.get_all(
        "Hotel Reservation",
        filters={"property": property_name, "status": ["in", ["Checked In", "Checked Out"]]},
        fields=["name", "status", "arrival_date", "departure_date", "folio", "guest"],
        limit_page_length=0,
    )
    signals["reservations_scanned"] = len(reservations)
    folio_names = list({row.folio for row in reservations if row.folio})
    folios = frappe.get_all(
        "Hotel Folio",
        filters={"property": property_name},
        fields=["name", "reservation", "status", "sales_invoice"],
        limit_page_length=0,
    )
    folio_map = {row.name: row for row in folios}
    charge_summary = _folio_charge_summary([row.name for row in folios])

    for reservation in reservations:
        if reservation.status == "Checked In" and not reservation.folio:
            findings.append({
                "finding_type": "Missing Folio", "severity": "Critical", "reference_doctype": "Hotel Reservation",
                "reference_name": reservation.name, "reservation": reservation.name, "confidence": 98,
                "description": f"Checked-in reservation {reservation.name} has no linked Hotel Folio.",
                "recommended_action": "Create or link the governed folio before posting any additional charge.",
                "evidence": {"status": reservation.status, "folio": reservation.folio},
            })
        if reservation.status == "Checked In" and reservation.departure_date and getdate(reservation.departure_date) < getdate(business_date):
            findings.append({
                "finding_type": "Stale In-house Stay", "severity": "Critical", "reference_doctype": "Hotel Reservation",
                "reference_name": reservation.name, "reservation": reservation.name, "confidence": 95,
                "description": f"Reservation {reservation.name} passed its departure date but remains Checked In.",
                "recommended_action": "Extend the stay or perform controlled checkout after reconciling the folio.",
                "evidence": {"departure_date": reservation.departure_date, "business_date": business_date},
            })
        if reservation.status == "Checked Out" and reservation.folio:
            folio = folio_map.get(reservation.folio)
            if folio and folio.status == "Open":
                findings.append({
                    "finding_type": "Open Folio After Checkout", "severity": "Critical", "reference_doctype": "Hotel Folio",
                    "reference_name": folio.name, "reservation": reservation.name, "folio": folio.name, "confidence": 97,
                    "description": f"Checked-out reservation {reservation.name} still has an open folio {folio.name}.",
                    "recommended_action": "Reconcile invoice and payment links before closing the folio.",
                    "evidence": {"reservation_status": reservation.status, "folio_status": folio.status},
                })

    for folio in folios:
        summary = charge_summary.get(folio.name, {})
        if summary.get("missing_tax"):
            findings.append({
                "finding_type": "Missing Tax Profile", "severity": "Warning", "reference_doctype": "Hotel Folio",
                "reference_name": folio.name, "reservation": folio.reservation, "folio": folio.name, "confidence": 90,
                "description": f"Folio {folio.name} contains {summary['missing_tax']} positive charge(s) without Hotel Tax Profile.",
                "recommended_action": "Assign the correct Hotel Tax Profile before creating or submitting the ERPNext invoice.",
                "evidence": summary,
            })
        if folio.status in ("Invoiced", "Closed"):
            invoice_status = frappe.db.get_value("Sales Invoice", folio.sales_invoice, "docstatus") if folio.sales_invoice else None
            if invoice_status != 1:
                findings.append({
                    "finding_type": "Invoice Link Mismatch", "severity": "Critical", "reference_doctype": "Hotel Folio",
                    "reference_name": folio.name, "reservation": folio.reservation, "folio": folio.name, "confidence": 99,
                    "description": f"Folio {folio.name} is {folio.status} but has no submitted ERPNext Sales Invoice.",
                    "recommended_action": "Reopen the operational folio or submit/relink the correct Sales Invoice through the governed billing workflow.",
                    "evidence": {"folio_status": folio.status, "sales_invoice": folio.sales_invoice, "invoice_docstatus": invoice_status},
                })

    failed_syncs = frappe.get_all(
        "Hotel ERP Sync Log", filters={"property": property_name, "status": "Failed"},
        fields=["name", "operation", "source_doctype", "source_name", "target_doctype", "target_name", "error_message"],
        limit_page_length=200,
    )
    signals["failed_syncs"] = len(failed_syncs)
    for sync in failed_syncs:
        findings.append({
            "finding_type": "Failed ERP Sync", "severity": "Critical", "reference_doctype": "Hotel ERP Sync Log",
            "reference_name": sync.name, "confidence": 100,
            "description": f"ERPNext synchronization failed for {sync.operation or sync.name}.",
            "recommended_action": "Resolve the root cause and use the existing idempotent retry/revision workflow. Do not create a replacement voucher manually.",
            "evidence": dict(sync),
        })

    duplicates = frappe.db.sql(
        """select idempotency_key, count(*) duplicate_count, group_concat(name order by name) logs
           from `tabHotel ERP Sync Log`
           where property=%s and status='Completed' and ifnull(idempotency_key,'')!=''
           group by idempotency_key having count(*)>1""",
        property_name,
        as_dict=True,
    )
    signals["duplicate_sync_keys"] = len(duplicates)
    for duplicate in duplicates:
        findings.append({
            "finding_type": "Duplicate Sync Key", "severity": "Critical", "reference_doctype": "Hotel ERP Sync Log",
            "reference_name": str(duplicate.logs).split(",")[0], "confidence": 100,
            "description": f"Multiple completed ERP sync records share idempotency key {duplicate.idempotency_key}.",
            "recommended_action": "Freeze related processing and reconcile the active ERPNext vouchers before any correction.",
            "evidence": dict(duplicate),
        })

    threshold = flt(config.get("cash_variance_threshold") or 1000)
    shifts = frappe.get_all(
        "Hotel Cashier Shift",
        filters={"property": property_name, "status": ["in", ["Closing Review", "Closed"]]},
        fields=["name", "status", "variance", "closed_at", "cashier"],
        limit_page_length=0,
    )
    for shift in shifts:
        if abs(flt(shift.variance)) > threshold:
            findings.append({
                "finding_type": "Cashier Variance", "severity": "Critical", "reference_doctype": "Hotel Cashier Shift",
                "reference_name": shift.name, "amount": abs(flt(shift.variance)), "confidence": 100,
                "description": f"Cashier shift {shift.name} has variance {shift.variance} above threshold {threshold}.",
                "recommended_action": "Recount cash and reconcile ERPNext Payment Entries before manager close.",
                "evidence": {"variance": shift.variance, "threshold": threshold, "cashier": shift.cashier, "status": shift.status},
            })

    kots = frappe.get_all(
        "Hotel Kitchen Ticket",
        filters={
            "property": property_name,
            "kot_date": ["<=", business_date],
            "status": ["not in", ["New", "Cancelled"]],
            "stock_posting_status": ["in", ["Queued", "Draft Created", "Failed", "Cancelled"]],
        },
        fields=["name", "restaurant_order", "status", "stock_posting_status", "stock_entry", "stock_error"],
        limit_page_length=0,
    )
    for kot in kots:
        severity = "Critical" if kot.stock_posting_status in ("Failed", "Cancelled") else "Warning"
        findings.append({
            "finding_type": "Restaurant Stock Posting", "severity": severity, "reference_doctype": "Hotel Kitchen Ticket",
            "reference_name": kot.name, "confidence": 98,
            "description": f"KOT {kot.name} has unresolved ERPNext stock posting status {kot.stock_posting_status}.",
            "recommended_action": "Resolve or repost through the KOT stock action. Do not create a manual duplicate Stock Entry.",
            "evidence": dict(kot),
        })

    signals["folios_scanned"] = len(folios)
    signals["findings_generated"] = len(findings)
    return findings, signals


@frappe.whitelist()
def run_night_audit_scan(property: str, business_date: str | None = None, triggered_by: str = "Manual") -> dict:
    _require_intelligence_access(property)
    business_date = getdate(business_date or nowdate())
    config_doc = _config(property, "Night Audit Anomaly")
    try:
        config = json.loads(config_doc.config_json or "{}")
    except Exception:
        config = {}
    run = _new_run(property, "Night Audit Anomaly", business_date, triggered_by)
    seen: set[str] = set()
    try:
        findings, signals = _collect_night_audit_findings(property, business_date, config)
        names = []
        for finding in findings:
            name = _upsert_finding(run, finding)
            names.append(name)
            seen.add(frappe.db.get_value("Hotel Night Audit Finding", name, "fingerprint"))

        stale = frappe.get_all(
            "Hotel Night Audit Finding",
            filters={"property": property, "business_date": business_date, "status": ["in", ["Open", "Acknowledged"]]},
            fields=["name", "fingerprint"], limit_page_length=0,
        )
        for old in stale:
            if old.fingerprint not in seen:
                frappe.db.set_value(
                    "Hotel Night Audit Finding", old.name,
                    {"status": "Resolved", "resolved_by": "Administrator", "resolution_notes": "Automatically resolved because the finding was absent on the latest governed scan."},
                    update_modified=False,
                )

        critical = sum(1 for row in findings if row["severity"] == "Critical")
        warning = sum(1 for row in findings if row["severity"] == "Warning")
        confidence = round(sum(flt(row.get("confidence")) for row in findings) / max(len(findings), 1), 2)
        recommendation = {
            "summary": {"total": len(findings), "critical": critical, "warning": warning},
            "finding_names": names,
            "requires_human_review": True,
            "financial_documents_created": 0,
        }
        decision = frappe.get_doc({
            "doctype": "Hotel Intelligence Decision",
            "property": property,
            "intelligence_run": run.name,
            "agent_type": "Night Audit Anomaly",
            "decision_type": "Review Night Audit Findings",
            "status": "Pending",
            "confidence": confidence,
            "idempotency_key": f"NIGHT-AUDIT:{property}:{business_date}:{run.name}",
            "input_snapshot_json": _json(signals),
            "recommendation_json": _json(recommendation),
        }).insert(ignore_permissions=True)
        for name in names:
            frappe.db.set_value("Hotel Night Audit Finding", name, "decision", decision.name, update_modified=False)
        summary = {"findings": len(findings), "decisions": 1, "critical": critical, "warning": warning, "decision": decision.name}
        _finish_run(run, "Completed", signals, summary)
        frappe.db.set_value("Hotel Intelligence Config", config_doc.name, {"last_run_at": now_datetime(), "last_run_status": "Completed", "last_error": None}, update_modified=False)
        return {"run": run.name, "decision": decision.name, "findings": names, "summary": summary}
    except Exception as exc:
        _finish_run(run, "Failed", {}, {"findings": 0, "decisions": 0}, str(exc))
        frappe.db.set_value("Hotel Intelligence Config", config_doc.name, {"last_run_at": now_datetime(), "last_run_status": "Failed", "last_error": str(exc)}, update_modified=False)
        raise


@frappe.whitelist()
def acknowledge_finding(finding: str) -> dict:
    doc = frappe.get_doc("Hotel Night Audit Finding", finding)
    _require_intelligence_access(doc.property)
    doc.check_permission("write")
    doc.status = "Acknowledged"
    doc.acknowledged_by = frappe.session.user
    doc.save()
    return {"finding": doc.name, "status": doc.status}


@frappe.whitelist()
def resolve_finding(finding: str, resolution_notes: str, false_positive: int = 0) -> dict:
    doc = frappe.get_doc("Hotel Night Audit Finding", finding)
    _require_intelligence_access(doc.property)
    doc.check_permission("write")
    doc.status = "False Positive" if int(false_positive or 0) else "Resolved"
    doc.resolution_notes = resolution_notes
    doc.resolved_by = frappe.session.user
    doc.save()
    return {"finding": doc.name, "status": doc.status}


@frappe.whitelist()
def approve_intelligence_decision(decision: str) -> dict:
    _require_intelligence_access()
    doc = frappe.get_doc("Hotel Intelligence Decision", decision)
    _require_intelligence_access(doc.property)
    if doc.status != "Pending":
        frappe.throw(_("Only Pending decisions can be approved."))
    doc.flags.intelligence_internal_update = True
    doc.status = "Approved"
    doc.approved_by = frappe.session.user
    doc.approved_at = now_datetime()
    doc.execution_result_json = _json({"executed": False, "reason": "Advisory decision approved for human action; no ERPNext document was created."})
    doc.save(ignore_permissions=True)
    return {"decision": doc.name, "status": doc.status}


@frappe.whitelist()
def reject_intelligence_decision(decision: str, reason: str) -> dict:
    doc = frappe.get_doc("Hotel Intelligence Decision", decision)
    _require_intelligence_access(doc.property)
    if doc.status != "Pending":
        frappe.throw(_("Only Pending decisions can be rejected."))
    doc.flags.intelligence_internal_update = True
    doc.status = "Rejected"
    doc.rejection_reason = reason
    doc.approved_by = frappe.session.user
    doc.approved_at = now_datetime()
    doc.save(ignore_permissions=True)
    return {"decision": doc.name, "status": doc.status}


@frappe.whitelist()
def attach_grounded_explanation(decision: str, rationale: str, suggestions_json: str | None = None) -> dict:
    doc = frappe.get_doc("Hotel Intelligence Decision", decision)
    _require_intelligence_access(doc.property)
    try:
        recommendation = json.loads(doc.recommendation_json or "{}")
        suggestions = json.loads(suggestions_json or "[]")
    except Exception:
        frappe.throw(_("Recommendation and suggestions must contain valid JSON."))
    guarded = ground_explanation(recommendation, rationale, suggestions)
    if not guarded["grounded"]:
        frappe.throw(_("Explanation contains a significant number not supported by the deterministic decision."))
    doc.flags.intelligence_internal_update = True
    doc.explanation = rationale + ("\n\nSuggestions:\n- " + "\n- ".join(guarded["suggestions"]) if guarded["suggestions"] else "")
    doc.save(ignore_permissions=True)
    return guarded


@frappe.whitelist()
def preview_payment_correction(payment_entry: str) -> dict:
    pe = frappe.get_doc("Payment Entry", payment_entry)
    pe.check_permission("read")
    reservation = getattr(pe, "custom_hotel_reservation", None)
    property_name = frappe.db.get_value("Hotel Reservation", reservation, "property") if reservation else None
    _require_finance_access(property_name)
    refundable = 0.0
    if reservation:
        from hotel_pms.front_desk import get_deposit_summary
        refundable = flt(get_deposit_summary(reservation).get("net_deposit"))
    original = flt(pe.paid_amount or pe.received_amount)
    plan = payment_correction_plan(
        docstatus=pe.docstatus,
        payment_type=pe.payment_type,
        hotel_transaction_type=getattr(pe, "custom_hotel_transaction_type", None),
        original_amount=original,
        refundable_amount=refundable,
    )
    return {
        "payment_entry": pe.name, "property": property_name, "reservation": reservation,
        "docstatus": pe.docstatus, "payment_type": pe.payment_type,
        "hotel_transaction_type": getattr(pe, "custom_hotel_transaction_type", None),
        "mode_of_payment": pe.mode_of_payment, **plan,
    }


@frappe.whitelist()
def approve_payment_correction(correction: str) -> dict:
    _require_finance_manager()
    doc = frappe.get_doc("Hotel Payment Correction", correction)
    if doc.status != "Pending Approval":
        frappe.throw(_("Only Pending Approval corrections can be approved."))
    doc.status = "Approved"
    doc.approved_by = frappe.session.user
    doc.approved_at = now_datetime()
    doc.save(ignore_permissions=True)
    return {"correction": doc.name, "status": doc.status}


@frappe.whitelist()
def reject_payment_correction(correction: str, reason: str) -> dict:
    _require_finance_manager()
    doc = frappe.get_doc("Hotel Payment Correction", correction)
    if doc.status not in ("Pending Approval", "Approved"):
        frappe.throw(_("This correction cannot be rejected in its current state."))
    doc.status = "Cancelled"
    doc.error_message = reason
    doc.save(ignore_permissions=True)
    return {"correction": doc.name, "status": doc.status}


@frappe.whitelist()
def execute_payment_correction(correction: str) -> dict:
    _require_finance_manager()
    frappe.db.sql("select name from `tabHotel Payment Correction` where name=%s for update", correction)
    doc = frappe.get_doc("Hotel Payment Correction", correction)
    if doc.status == "Executed":
        return {"correction": doc.name, "status": doc.status, "result_doctype": doc.result_doctype, "result_name": doc.result_name, "already_executed": True}
    if doc.status != "Approved":
        frappe.throw(_("Correction must be approved before execution."))
    pe = frappe.get_doc("Payment Entry", doc.payment_entry)
    try:
        if doc.requested_action == "Delete Draft":
            if pe.docstatus != 0:
                frappe.throw(_("Payment Entry is no longer Draft."))
            frappe.delete_doc("Payment Entry", pe.name)
            result = {"deleted_draft": pe.name, "financial_ledger_rows_created": 0}
            doc.result_doctype = None
            doc.result_name = None
        elif doc.requested_action == "Create Refund":
            if not doc.reservation:
                frappe.throw(_("Hotel Reservation link is required for the governed refund path."))
            from hotel_pms.front_desk import create_refund_payment_entry
            response = create_refund_payment_entry(
                reservation=doc.reservation,
                amount=flt(doc.amount),
                mode_of_payment=doc.mode_of_payment,
                idempotency_key=f"CORRECTION-{doc.name}",
                reference_no=f"Correction {doc.name}",
                reference_date=nowdate(),
            )
            result = {**response, "source_payment_entry": pe.name, "submitted_automatically": False}
            doc.result_doctype = "Payment Entry"
            doc.result_name = response["payment_entry"]
        else:
            frappe.throw(_("Manual Review actions are not executable by the system."))
        doc.status = "Executed"
        doc.executed_at = now_datetime()
        doc.execution_result_json = _json(result)
        doc.error_message = None
        doc.save(ignore_permissions=True)
        return {"correction": doc.name, "status": doc.status, "result": result}
    except Exception as exc:
        doc.status = "Failed"
        doc.error_message = str(exc)
        doc.execution_result_json = _json({"error": str(exc)})
        doc.save(ignore_permissions=True)
        raise


REGISTRY = [
    {
        "integration_key": "erpnext-native-accounting", "provider_name": "ERPNext Native Accounting", "category": "ERP & Accounting",
        "maturity_status": "Shipped", "enabled_in_product": 1, "adapter_path": "hotel_pms.integrations", "documentation": "docs/ARCHITECTURE.md",
        "supports_test_connection": 1, "financial_behavior": "ERPNext Native",
        "description": "Sales Invoice, POS Invoice, Payment Entry, Purchase Invoice, Stock Entry and their ledgers remain authoritative.",
    },
    {
        "integration_key": "meta-whatsapp-cloud", "provider_name": "Meta WhatsApp Cloud API", "category": "Guest Messaging",
        "maturity_status": "Shipped", "enabled_in_product": 1, "adapter_path": "hotel_pms.communications", "documentation": "docs/ADOPTION_V100_RC2.md",
        "supports_test_connection": 1, "financial_behavior": "No Financial Posting",
        "description": "Property-scoped asynchronous WhatsApp templates, inbound messages and delivery status.",
    },
    {
        "integration_key": "hotel-outbound-webhooks", "provider_name": "Hotel PMS Outbound Webhooks", "category": "Webhooks",
        "maturity_status": "Shipped", "enabled_in_product": 1, "adapter_path": "hotel_pms.webhooks", "documentation": "docs/PLATFORM_HARDENING_V090.md",
        "supports_test_connection": 1, "financial_behavior": "No Financial Posting",
        "description": "HMAC-signed property-scoped events with retry and dead-letter handling.",
    },
    {
        "integration_key": "hotel-api-v1", "provider_name": "Hotel PMS API v1", "category": "API",
        "maturity_status": "Shipped", "enabled_in_product": 1, "adapter_path": "hotel_pms.api.v1", "documentation": "docs/openapi-v1.json",
        "supports_test_connection": 1, "financial_behavior": "No Financial Posting",
        "description": "Versioned API with property scope, idempotency and generated OpenAPI/Postman artifacts.",
    },
    {
        "integration_key": "generic-csv-migration", "provider_name": "Generic CSV Migration", "category": "Data Migration",
        "maturity_status": "Shipped", "enabled_in_product": 1, "adapter_path": "hotel_pms.migration", "documentation": "docs/PLATFORM_HARDENING_MANUAL_V090.md",
        "supports_test_connection": 1, "financial_behavior": "No Financial Posting",
        "description": "Dry-run and row-level import review. Legacy deposits remain manual review items.",
    },
    {
        "integration_key": "generic-ical-distribution", "provider_name": "Generic iCal Distribution", "category": "Channel Manager",
        "maturity_status": "Shipped", "enabled_in_product": 1, "adapter_path": "hotel_pms.distribution", "documentation": "docs/DISTRIBUTION_TURNOVER_RC8.md",
        "supports_test_connection": 1, "financial_behavior": "No Financial Posting",
        "description": "Secure per-room iCal import/export with token rotation, SSRF guards, buffer days and overlap review.",
    },
    {
        "integration_key": "generic-json-distribution", "provider_name": "Generic JSON Distribution Webhook", "category": "Channel Manager",
        "maturity_status": "Shipped", "enabled_in_product": 1, "adapter_path": "hotel_pms.distribution", "documentation": "docs/DISTRIBUTION_TURNOVER_RC8.md",
        "supports_test_connection": 1, "financial_behavior": "No Financial Posting",
        "description": "Property-scoped normalized booking webhook. Creates only Hotel Reservation operational records; ERPNext posting stays downstream.",
    },
    {
        "integration_key": "channex-channel-adapter", "provider_name": "Channex Channel Adapter", "category": "Channel Manager",
        "maturity_status": "Adapter", "enabled_in_product": 1, "adapter_path": "hotel_pms.channels", "documentation": "docs/DISTRIBUTION_TURNOVER_RC8.md",
        "supports_test_connection": 0, "financial_behavior": "No Financial Posting",
        "description": "Provider seam registered but not certified in RC8. Partner credentials and field-level certification are required before Live status.",
    },
    {
        "integration_key": "staah-channel-adapter", "provider_name": "STAAH Channel Adapter", "category": "Channel Manager",
        "maturity_status": "Adapter", "enabled_in_product": 1, "adapter_path": "hotel_pms.channels", "documentation": "docs/DISTRIBUTION_TURNOVER_RC8.md",
        "supports_test_connection": 0, "financial_behavior": "No Financial Posting",
        "description": "Provider seam registered but not certified in RC8.",
    },
    {
        "integration_key": "aiosell-channel-adapter", "provider_name": "AioSell Channel Adapter", "category": "Channel Manager",
        "maturity_status": "Adapter", "enabled_in_product": 1, "adapter_path": "hotel_pms.channels", "documentation": "docs/DISTRIBUTION_TURNOVER_RC8.md",
        "supports_test_connection": 0, "financial_behavior": "No Financial Posting",
        "description": "Provider seam registered but not certified in RC8.",
    },
]

DEFAULT_GO_LIVE_CHECKS = [
    ("PROPERTY_SCOPE", "Property isolation test passed"),
    ("CREDENTIALS", "Credentials stored securely and rotated"),
    ("TEST_CONNECTION", "Test connection passed"),
    ("IDEMPOTENCY", "Retry and idempotency behavior verified"),
    ("ERROR_ALERT", "Permanent failure alert verified"),
    ("RUNBOOK", "GO_LIVE runbook and owner approved"),
]


@frappe.whitelist()
def seed_integration_registry() -> dict:
    _require_intelligence_access()
    created = updated = 0
    for row in REGISTRY:
        existing = frappe.db.exists("Hotel Integration Definition", row["integration_key"])
        if existing:
            doc = frappe.get_doc("Hotel Integration Definition", existing)
            doc.update(row)
            updated += 1
        else:
            doc = frappe.get_doc({"doctype": "Hotel Integration Definition", **row})
            created += 1
        doc.set("go_live_checks", [])
        for code, title in DEFAULT_GO_LIVE_CHECKS:
            doc.append("go_live_checks", {"check_code": code, "title": title, "mandatory": 1, "status": "Pending"})
        doc.save(ignore_permissions=True) if existing else doc.insert(ignore_permissions=True)
    return {"created": created, "updated": updated, "total": len(REGISTRY)}


def _ensure_connection_checks(connection) -> None:
    if connection.go_live_checks:
        return
    definition = frappe.get_doc("Hotel Integration Definition", connection.integration)
    for row in definition.go_live_checks:
        connection.append("go_live_checks", {"check_code": row.check_code, "title": row.title, "mandatory": row.mandatory, "status": "Pending"})


@frappe.whitelist()
def test_integration_connection(connection: str) -> dict:
    doc = frappe.get_doc("Hotel Integration Connection", connection)
    _require_intelligence_access(doc.property)
    _ensure_connection_checks(doc)
    key = doc.integration
    result: dict[str, Any]
    try:
        if key == "erpnext-native-accounting":
            installed = set(frappe.get_installed_apps())
            required = {
                "Sales Invoice": ("custom_hotel_sync_key",),
                "POS Invoice": ("custom_hotel_sync_key",),
                "Payment Entry": ("custom_hotel_sync_key", "custom_hotel_reservation"),
                "Purchase Invoice": ("custom_hotel_sync_key",),
                "Stock Entry": ("custom_hotel_sync_key", "custom_hotel_kitchen_ticket"),
            }
            missing = {dt: [field for field in fields if not frappe.get_meta(dt).has_field(field)] for dt, fields in required.items()}
            missing = {dt: fields for dt, fields in missing.items() if fields}
            result = {"passed": "erpnext" in installed and not missing, "installed_apps": sorted(installed), "missing_fields": missing}
        elif key == "meta-whatsapp-cloud":
            channel = frappe.db.get_value("Hotel Channel Connection", {"property": doc.property, "channel": "WhatsApp", "provider": "Meta Cloud API", "enabled": 1}, ["name", "last_verified_at", "last_error"], as_dict=True)
            result = {"passed": bool(channel and channel.last_verified_at and not channel.last_error), "channel_connection": channel}
        elif key == "hotel-outbound-webhooks":
            count = frappe.db.count("Hotel Webhook Subscription", {"property": doc.property, "enabled": 1})
            result = {"passed": count > 0, "active_subscriptions": count}
        elif key == "hotel-api-v1":
            __import__("hotel_pms.api.v1")
            result = {"passed": True, "module": "hotel_pms.api.v1"}
        elif key == "generic-csv-migration":
            __import__("hotel_pms.migration")
            result = {"passed": frappe.db.exists("DocType", "Hotel Migration Batch"), "module": "hotel_pms.migration"}
        elif key in ("generic-ical-distribution", "generic-json-distribution"):
            provider = "Generic iCal" if key == "generic-ical-distribution" else "Generic JSON"
            connections = frappe.get_all("Hotel Distribution Connection", filters={"property": doc.property, "provider": provider, "enabled": 1}, fields=["name", "status", "last_test_status"])
            passed = bool(connections) and all(str(row.last_test_status or "").startswith("OK") for row in connections)
            result = {"passed": passed, "provider": provider, "connections": connections}
        else:
            result = {"passed": False, "error": "No shipped test adapter is registered for this integration."}
    except Exception as exc:
        result = {"passed": False, "error": str(exc)}
    now = now_datetime()
    previous_status = doc.status
    doc.last_tested_at = now
    doc.last_test_status = "Passed" if result["passed"] else "Failed"
    doc.last_test_result_json = _json(result)
    if result["passed"]:
        doc.last_success_at = now
        # Preserve an already approved Ready/Live state. A health check must not
        # silently downgrade a production connection merely because it passed.
        doc.status = previous_status if previous_status in ("Ready", "Live") else "Tested"
    else:
        doc.last_failure_at = now
        doc.failure_count = int(doc.failure_count or 0) + 1
        doc.status = "Failed"
    for row in doc.go_live_checks:
        if row.check_code == "TEST_CONNECTION":
            row.status = "Passed" if result["passed"] else "Failed"
            row.evidence = _json(result)[:1000]
            row.checked_at = now
            row.checked_by = frappe.session.user
    doc.save(ignore_permissions=True)
    return result


@frappe.whitelist()
def get_intelligence_dashboard(property: str, business_date: str | None = None) -> dict:
    _require_intelligence_access(property)
    business_date = getdate(business_date or nowdate())
    finding_filters = {"property": property, "business_date": business_date}
    findings = frappe.get_all(
        "Hotel Night Audit Finding", filters=finding_filters,
        fields=["name", "severity", "finding_type", "status", "reference_doctype", "reference_name", "description", "recommended_action", "amount", "modified"],
        order_by="modified desc", limit_page_length=100,
    )
    severity_order={"Critical":0,"Warning":1,"Info":2}
    findings=sorted(findings,key=lambda row:(severity_order.get(row.severity,3),str(row.modified)),reverse=False)
    decisions = frappe.get_all(
        "Hotel Intelligence Decision", filters={"property": property},
        fields=["name", "agent_type", "decision_type", "confidence", "status", "modified"],
        order_by="modified desc", limit_page_length=20,
    )
    definitions = frappe.get_all("Hotel Integration Definition", fields=["name", "provider_name", "category", "maturity_status"], order_by="category, provider_name", limit_page_length=0)
    connection_map = {row.integration: row.status for row in frappe.get_all("Hotel Integration Connection", filters={"property": property}, fields=["integration", "status"], limit_page_length=0)}
    integrations = [{**dict(row), "connection_status": connection_map.get(row.name)} for row in definitions]
    cards = {
        "Critical Open": sum(1 for row in findings if row.severity == "Critical" and row.status in ("Open", "Acknowledged")),
        "Warning Open": sum(1 for row in findings if row.severity == "Warning" and row.status in ("Open", "Acknowledged")),
        "Pending Decisions": sum(1 for row in decisions if row.status == "Pending"),
        "Live Integrations": sum(1 for row in integrations if row.get("connection_status") == "Live"),
        "Registry Shipped": sum(1 for row in integrations if row["maturity_status"] == "Shipped"),
    }
    return {"business_date": business_date, "cards": cards, "findings": findings, "decisions": decisions, "integrations": integrations}


def run_scheduled_intelligence() -> dict:
    processed = 0
    errors = []
    configs = frappe.get_all("Hotel Intelligence Config", filters={"agent_type": "Night Audit Anomaly", "enabled": 1}, fields=["name", "property"])
    for config in configs:
        try:
            run_night_audit_scan(config.property, getdate(nowdate()) - timedelta(days=1), "Schedule")
            processed += 1
        except Exception as exc:
            errors.append({"config": config.name, "error": str(exc)})
            frappe.log_error(frappe.get_traceback(), f"Hotel intelligence scheduler failed: {config.name}")
    return {"processed": processed, "errors": errors}
