from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from hotel_pms import __version__
from hotel_pms.platform import assigned_properties, is_privileged
from hotel_pms.production_validation import (
    create_validation_evidence,
    current_environment,
    record_rehearsal,
    verify_release_manifest,
)
from hotel_pms.staging_execution_rules import (
    duplicate_active_keys,
    evidence_matches_environment,
    evidence_sha256,
    redact_payload,
    summarize_execution_checks,
)

PREFLIGHT_REQUIRED = {
    "INSTALLED_APPS",
    "MANIFEST",
    "DATABASE",
    "REQUIRED_DOCTYPES",
    "ERP_CUSTOM_FIELDS",
    "SCHEDULER",
    "WORKER_HEARTBEAT",
    "SITE_SECURITY",
    "STORAGE",
    "PROPERTY_ACCESS",
}

SMOKE_REQUIRED = {
    "PREFLIGHT",
    "SETTINGS",
    "PROPERTY_READ",
    "RESERVATION_READ",
    "FOLIO_READ",
    "ERP_SYNC_READ",
    "FINANCE_LINK_FIELDS",
    "STOCK_LINK_FIELDS",
    "API_IMPORTS",
}

CORE_DOCTYPES = (
    "Hotel Property",
    "Hotel Reservation",
    "Hotel Folio",
    "Hotel Production Gate Run",
    "Hotel Release Manifest",
    "Hotel Rehearsal Run",
    "Hotel Validation Evidence",
    "Hotel Parallel Run Batch",
    "Hotel ERP Sync Log",
)

ERP_CUSTOM_FIELDS = {
    "Sales Invoice": ("custom_hotel_sync_key",),
    "POS Invoice": ("custom_hotel_sync_key", "custom_hotel_restaurant_order"),
    "Payment Entry": ("custom_hotel_sync_key", "custom_hotel_reservation"),
    "Purchase Invoice": ("custom_hotel_sync_key",),
    "Stock Entry": ("custom_hotel_sync_key", "custom_hotel_kitchen_ticket"),
}


def _require_manager() -> None:
    if not is_privileged() and "Hotel Manager" not in frappe.get_roles():
        frappe.throw(_("Hotel Manager or System Manager role required."), frappe.PermissionError)


def _validate_property(property_name: str | None) -> None:
    if property_name and property_name not in assigned_properties():
        frappe.throw(_("Not permitted for this property."), frappe.PermissionError)


def _row(code: str, passed: bool, measured=None, expected=None, details=None, warning: bool = False) -> dict:
    return {
        "code": code,
        "status": "Warning" if warning and passed else ("Passed" if passed else "Failed"),
        "measured": measured,
        "expected": expected,
        "details": details,
    }


def _safe_db_value(query: str):
    rows = frappe.db.sql(query)
    return rows[0][0] if rows and rows[0] else None


def _write_gate_check(gate, code: str, status: str, measured, threshold: str, details: dict | str, evidence_url: str | None = None) -> None:
    row = next((item for item in gate.checks if item.check_code == code), None)
    if not row:
        return
    row.status = status
    row.measured_value = str(measured if measured is not None else "")
    row.threshold = threshold
    row.details = details if isinstance(details, str) else json.dumps(redact_payload(details), sort_keys=True, default=str)
    row.evidence_url = evidence_url
    row.checked_at = now_datetime()
    row.checked_by = frappe.session.user
    gate.flags.production_gate_internal_update = True
    gate.save(ignore_permissions=True)


def _gate(gate_run: str):
    gate = frappe.get_doc("Hotel Production Gate Run", gate_run)
    _validate_property(gate.property)
    return gate


def _custom_field_check() -> tuple[bool, dict]:
    missing: dict[str, list[str]] = {}
    for doctype, fields in ERP_CUSTOM_FIELDS.items():
        meta = frappe.get_meta(doctype)
        absent = [field for field in fields if not meta.has_field(field)]
        if absent:
            missing[doctype] = absent
    return not missing, missing


def environment_preflight(gate_run: str | None = None) -> dict:
    """Read-only environment inspection suitable for immutable evidence."""
    _require_manager()
    gate = _gate(gate_run) if gate_run else None
    env = current_environment()
    checks: list[dict] = []

    apps = frappe.get_installed_apps()
    checks.append(_row("INSTALLED_APPS", all(app in apps for app in ("frappe", "erpnext", "hotel_pms")), apps, "frappe, erpnext, hotel_pms"))

    if gate and gate.release_manifest:
        manifest = verify_release_manifest(gate.release_manifest)
        checks.append(_row("MANIFEST", bool(manifest.get("passed")), gate.release_manifest, "frozen manifest matches installed artifact", manifest.get("blockers")))
    else:
        checks.append(_row("MANIFEST", False, "missing", "gate run with frozen manifest"))

    try:
        db_version = _safe_db_value("select version()")
        isolation = None
        for query in ("select @@transaction_isolation", "select @@tx_isolation"):
            try:
                isolation = _safe_db_value(query)
                break
            except Exception:
                continue
        checks.append(_row("DATABASE", bool(db_version), {"version": db_version, "isolation": isolation}, "reachable MariaDB"))
    except Exception as exc:
        checks.append(_row("DATABASE", False, details=str(exc)))

    missing_doctypes = [name for name in CORE_DOCTYPES if not frappe.db.exists("DocType", name)]
    checks.append(_row("REQUIRED_DOCTYPES", not missing_doctypes, len(CORE_DOCTYPES) - len(missing_doctypes), len(CORE_DOCTYPES), missing_doctypes))

    fields_ok, missing_fields = _custom_field_check()
    checks.append(_row("ERP_CUSTOM_FIELDS", fields_ok, "complete" if fields_ok else "missing", "required ERPNext links and sync keys", missing_fields))

    paused = int(getattr(frappe.conf, "pause_scheduler", 0) or 0)
    checks.append(_row("SCHEDULER", paused == 0, {"pause_scheduler": paused}, "active"))

    settings = frappe.get_single("Hotel PMS Settings")
    heartbeat = settings.get("last_worker_heartbeat")
    age_minutes = None
    if heartbeat:
        age_minutes = round((now_datetime() - get_datetime(heartbeat)).total_seconds() / 60, 2)
    checks.append(_row("WORKER_HEARTBEAT", age_minutes is not None and age_minutes < 15, age_minutes, "<15 minutes"))

    developer_mode = int(getattr(frappe.conf, "developer_mode", 0) or 0)
    encryption_present = bool(getattr(frappe.conf, "encryption_key", None))
    host_name = str(getattr(frappe.conf, "host_name", "") or "")
    environment_name = gate.environment_name if gate else "Staging"
    security_ok = encryption_present and (environment_name == "Development" or developer_mode == 0)
    checks.append(_row("SITE_SECURITY", security_ok, {"developer_mode": developer_mode, "encryption_key_present": encryption_present, "https_host": host_name.startswith("https://")}, "encryption key present; developer mode off outside development"))

    site_path = Path(frappe.get_site_path()).resolve()
    usage = shutil.disk_usage(site_path)
    free_gb = round(usage.free / (1024 ** 3), 2)
    writable = os.access(site_path, os.W_OK) and os.access(Path(frappe.get_site_path("private", "files")), os.W_OK)
    checks.append(_row("STORAGE", writable and free_gb >= 2, {"site_path": str(site_path), "free_gb": free_gb, "writable": writable}, ">=2 GB free and writable"))

    from hotel_pms.platform import get_access_review

    access = get_access_review()
    checks.append(_row("PROPERTY_ACCESS", int(access.get("users_missing_property") or 0) == 0, access, "0 hotel users missing property assignment"))

    summary = summarize_execution_checks(checks, PREFLIGHT_REQUIRED)
    return {"release_version": __version__, "environment": env, "gate_run": gate.name if gate else None, "checks": checks, "summary": summary}


@frappe.whitelist()
def capture_staging_preflight(gate_run: str) -> dict:
    _require_manager()
    gate = _gate(gate_run)
    result = environment_preflight(gate_run)
    payload = redact_payload(result)
    digest = evidence_sha256(payload)
    evidence = create_validation_evidence(
        gate_run,
        "STAGING_PREFLIGHT",
        "Command Output",
        description=json.dumps(payload, sort_keys=True, default=str),
        checksum_sha256=digest,
        metadata_json={**current_environment(), "summary": result["summary"]},
    )
    _write_gate_check(gate, "STAGING_PREFLIGHT", result["summary"]["status"], digest, "all required preflight checks Passed", result, evidence.name)
    return {"result": result, "evidence": evidence}


def _smoke_checks(gate_run: str) -> list[dict]:
    gate = _gate(gate_run)
    preflight = environment_preflight(gate_run)
    checks = [_row("PREFLIGHT", preflight["summary"]["status"] == "Passed", preflight["summary"], "Passed")]

    try:
        settings = frappe.get_single("Hotel PMS Settings")
        checks.append(_row("SETTINGS", bool(settings.name), settings.name, "Hotel PMS Settings readable"))
    except Exception as exc:
        checks.append(_row("SETTINGS", False, details=str(exc)))

    property_filters = {"name": gate.property} if gate.property else {}
    try:
        count = frappe.db.count("Hotel Property", property_filters)
        checks.append(_row("PROPERTY_READ", count > 0, count, ">0 property"))
    except Exception as exc:
        checks.append(_row("PROPERTY_READ", False, details=str(exc)))

    linked_filters = {"property": gate.property} if gate.property else {}
    for code, doctype in (("RESERVATION_READ", "Hotel Reservation"), ("FOLIO_READ", "Hotel Folio"), ("ERP_SYNC_READ", "Hotel ERP Sync Log")):
        try:
            count = frappe.db.count(doctype, linked_filters)
            checks.append(_row(code, True, count, "read query succeeds"))
        except Exception as exc:
            checks.append(_row(code, False, details=str(exc)))

    fields_ok, missing_fields = _custom_field_check()
    checks.append(_row("FINANCE_LINK_FIELDS", fields_ok, missing_fields or "complete", "ERPNext financial documents have Hotel PMS sync fields"))
    stock_meta = frappe.get_meta("Stock Entry")
    stock_ok = stock_meta.has_field("custom_hotel_sync_key") and stock_meta.has_field("custom_hotel_kitchen_ticket")
    checks.append(_row("STOCK_LINK_FIELDS", stock_ok, {"sync_key": stock_meta.has_field("custom_hotel_sync_key"), "kitchen_ticket": stock_meta.has_field("custom_hotel_kitchen_ticket")}, "Stock Entry integration fields present"))

    imports = (
        "hotel_pms.api.v1",
        "hotel_pms.front_desk",
        "hotel_pms.billing",
        "hotel_pms.services",
        "hotel_pms.fnb_inventory",
        "hotel_pms.communications",
    )
    import_errors = {}
    for module in imports:
        try:
            __import__(module)
        except Exception as exc:
            import_errors[module] = str(exc)
    checks.append(_row("API_IMPORTS", not import_errors, len(imports) - len(import_errors), len(imports), import_errors))
    return checks


@frappe.whitelist()
def run_smoke_suite(gate_run: str) -> dict:
    _require_manager()
    gate = _gate(gate_run)
    started = now_datetime()
    checks = _smoke_checks(gate_run)
    summary = summarize_execution_checks(checks, SMOKE_REQUIRED)
    completed = now_datetime()
    metadata = {**current_environment(), "checks": checks, "summary": summary, "gate_run": gate.name}
    rehearsal = record_rehearsal(
        "Smoke",
        gate.environment_name,
        "Passed" if summary["status"] == "Passed" else "Failed",
        started,
        completed,
        property=gate.property,
        source_version=__version__,
        result_summary=json.dumps(redact_payload(metadata), sort_keys=True, default=str),
        command="hotel_pms.staging_execution.run_smoke_suite",
        evidence_sha256=evidence_sha256(metadata),
        metadata_json=metadata,
    )
    _write_gate_check(gate, "SMOKE_REHEARSAL", "Passed" if summary["status"] == "Passed" else "Failed", rehearsal.name, "Passed Smoke rehearsal for exact source/image", metadata, rehearsal.name)
    return {"rehearsal": rehearsal, "checks": checks, "summary": summary}


def _active_sync_key_duplicates() -> list[dict]:
    rows: list[dict] = []
    for doctype in ("Sales Invoice", "POS Invoice", "Payment Entry", "Purchase Invoice", "Stock Entry"):
        meta = frappe.get_meta(doctype)
        if not meta.has_field("custom_hotel_sync_key"):
            continue
        data = frappe.get_all(
            doctype,
            filters={"custom_hotel_sync_key": ["is", "set"], "docstatus": ["<", 2]},
            fields=["name", "docstatus", "custom_hotel_sync_key"],
            limit_page_length=0,
        )
        rows.extend({"doctype": doctype, "name": item.name, "docstatus": item.docstatus, "sync_key": item.custom_hotel_sync_key} for item in data)
    return duplicate_active_keys(rows)


@frappe.whitelist()
def capture_reconciliation_snapshot(gate_run: str, from_date=None, to_date=None) -> dict:
    _require_manager()
    gate = _gate(gate_run)
    from hotel_pms.production_gate import accounting_reconciliation, stock_reconciliation

    start = from_date or gate.reconciliation_from_date
    end = to_date or gate.reconciliation_to_date
    accounting = accounting_reconciliation(gate.property, start, end)
    stock = stock_reconciliation(gate.property, start, end)
    duplicate_keys = _active_sync_key_duplicates()
    result = {
        "release_version": __version__,
        "gate_run": gate.name,
        "property": gate.property,
        "from_date": start,
        "to_date": end,
        "accounting": accounting,
        "stock": stock,
        "duplicate_active_sync_keys": duplicate_keys,
    }
    passed = not accounting.get("blockers") and not stock.get("blockers") and not duplicate_keys
    result["status"] = "Passed" if passed else "Failed"
    digest = evidence_sha256(result)
    evidence = create_validation_evidence(
        gate_run,
        "RECON_SNAPSHOT",
        "Command Output",
        description=json.dumps(redact_payload(result), sort_keys=True, default=str),
        checksum_sha256=digest,
        metadata_json={**current_environment(), "status": result["status"], "from_date": start, "to_date": end},
    )
    _write_gate_check(gate, "RECON_SNAPSHOT", result["status"], digest, "accounting, stock and active sync-key checks Passed", result, evidence.name)
    return {"result": result, "evidence": evidence}


def latest_matching_evidence(gate_run: str, check_code: str) -> dict | None:
    gate = frappe.get_doc("Hotel Production Gate Run", gate_run)
    rows = frappe.get_all(
        "Hotel Validation Evidence",
        filters={"gate_run": gate.name, "check_code": check_code},
        fields=["name", "check_code", "checksum_sha256", "metadata_json", "captured_at"],
        order_by="captured_at desc",
        limit=1,
    )
    if not rows:
        return None
    row = rows[0]
    try:
        metadata = json.loads(row.metadata_json or "{}")
    except Exception:
        metadata = {}
    row["metadata"] = metadata
    row["matches_current_environment"] = evidence_matches_environment(metadata, current_environment())
    return row


@frappe.whitelist()
def build_cutover_bundle(gate_run: str) -> dict:
    _require_manager()
    gate = _gate(gate_run)
    from hotel_pms.production_gate import get_gate_dashboard
    from hotel_pms.production_validation import validation_gate_results

    preflight = environment_preflight(gate_run)
    dashboard = get_gate_dashboard(gate_run)
    validation = validation_gate_results(gate)
    evidence_rows = frappe.get_all(
        "Hotel Validation Evidence",
        filters={"gate_run": gate.name},
        fields=["name", "check_code", "evidence_type", "checksum_sha256", "captured_at", "captured_by"],
        order_by="captured_at asc",
        limit_page_length=0,
    )
    payload = redact_payload(
        {
            "schema": "hotel-pms-cutover-bundle-v1",
            "generated_at": now_datetime(),
            "generated_by": frappe.session.user,
            "environment": current_environment(),
            "gate": dashboard,
            "validation": validation,
            "preflight": preflight,
            "evidence_index": evidence_rows,
        }
    )
    content = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    file_name = f"hotel-pms-cutover-{gate.name}-{digest[:12]}.json"
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": file_name,
            "is_private": 1,
            "content": content,
            "attached_to_doctype": "Hotel Production Gate Run",
            "attached_to_name": gate.name,
        }
    )
    file_doc.insert(ignore_permissions=True)
    evidence = create_validation_evidence(
        gate_run,
        "CUTOVER_BUNDLE",
        "File",
        evidence_file=file_doc.file_url,
        description="Private cutover bundle generated from the current frozen source and gate evidence.",
        checksum_sha256=digest,
        metadata_json={**current_environment(), "schema": payload["schema"], "file_url": file_doc.file_url},
    )
    _write_gate_check(gate, "CUTOVER_BUNDLE", "Passed", digest, "private bundle checksum matches captured evidence", {"file_url": file_doc.file_url, "evidence": evidence.name}, file_doc.file_url)
    return {"file_url": file_doc.file_url, "sha256": digest, "evidence": evidence, "schema": payload["schema"]}
