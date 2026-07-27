from __future__ import annotations

import frappe

FINANCIAL_DOCTYPES = (
    "Sales Invoice",
    "POS Invoice",
    "Payment Entry",
    "Journal Entry",
    "Purchase Invoice",
    "Stock Entry",
)


def financial_document_counts() -> dict:
    counts = {doctype: frappe.db.count(doctype) for doctype in FINANCIAL_DOCTYPES}
    counts["GL Entry"] = frappe.db.count("GL Entry")
    counts["Stock Ledger Entry"] = frappe.db.count("Stock Ledger Entry")
    return counts


def run_rc7_smoke(property_name: str) -> dict:
    from hotel_pms.intelligence import run_night_audit_scan, seed_integration_registry

    before = financial_document_counts()
    registry = seed_integration_registry()
    first = run_night_audit_scan(property_name, frappe.utils.nowdate(), "API")
    count_after_first = frappe.db.count(
        "Hotel Night Audit Finding",
        {"property": property_name, "business_date": frappe.utils.nowdate()},
    )
    second = run_night_audit_scan(property_name, frappe.utils.nowdate(), "API")
    count_after_second = frappe.db.count(
        "Hotel Night Audit Finding",
        {"property": property_name, "business_date": frappe.utils.nowdate()},
    )
    after = financial_document_counts()
    if before != after:
        frappe.throw(
            f"RC7 read-only intelligence smoke changed financial/ledger counts: before={before}, after={after}"
        )
    if count_after_first != count_after_second:
        frappe.throw(
            f"RC7 finding upsert is not idempotent: first={count_after_first}, second={count_after_second}"
        )
    return {
        "before": before,
        "after": after,
        "registry": registry,
        "first_scan": first,
        "second_scan": second,
        "finding_count": count_after_second,
        "passed": True,
    }


# Backward-compatible alias for older external execution tooling.
def run_rc6_smoke(property_name: str) -> dict:
    return run_rc7_smoke(property_name)
