from __future__ import annotations

import frappe

FINANCIAL_DOCTYPES = ("Sales Invoice", "POS Invoice", "Payment Entry", "Journal Entry", "Purchase Invoice", "Stock Entry")


def financial_document_counts() -> dict:
    return {doctype: frappe.db.count(doctype) for doctype in FINANCIAL_DOCTYPES}


def run_rc6_smoke(property_name: str) -> dict:
    from hotel_pms.intelligence import run_night_audit_scan, seed_integration_registry

    before = financial_document_counts()
    registry = seed_integration_registry()
    scan = run_night_audit_scan(property_name, frappe.utils.nowdate(), "API")
    after = financial_document_counts()
    if before != after:
        frappe.throw(f"RC6 read-only intelligence smoke changed financial document counts: before={before}, after={after}")
    return {"before": before, "after": after, "registry": registry, "scan": scan, "passed": True}
