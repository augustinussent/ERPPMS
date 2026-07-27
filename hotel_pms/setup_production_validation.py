from __future__ import annotations

import frappe


def setup_production_validation() -> None:
    indexes = {
        "Hotel Release Manifest": [["release_version", "status"], ["source_fingerprint"]],
        "Hotel Rehearsal Run": [["property", "run_type", "environment_name", "release_version", "status"]],
        "Hotel Parallel Run Batch": [["property", "to_date", "status"]],
        "Hotel Validation Evidence": [["gate_run", "check_code"], ["property", "captured_at"]],
        "Hotel Production Gate Run": [["release_manifest", "promotion_status"]],
    }
    for doctype, groups in indexes.items():
        if not frappe.db.exists("DocType", doctype):
            continue
        for fields in groups:
            try:
                frappe.db.add_index(doctype, fields)
            except Exception:
                pass
