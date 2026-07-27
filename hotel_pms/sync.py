from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

import frappe
from frappe import _
from frappe.exceptions import DuplicateEntryError
from frappe.utils import now_datetime

SYNC_FIELD = "custom_hotel_sync_key"
MAX_SYNC_KEY_LENGTH = 130


def make_sync_key(operation: str, *parts: Any) -> str:
    raw = ":".join([operation, *[str(part or "-") for part in parts]])
    if len(raw) <= MAX_SYNC_KEY_LENGTH:
        return raw
    digest = hashlib.sha256(raw.encode()).hexdigest()[:32]
    return f"{operation}:{digest}"


def payload_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _targets_for_base(target_doctype: str, base_key: str) -> list:
    fields = ["name", "docstatus", SYNC_FIELD, "creation"]
    exact = frappe.get_all(target_doctype, filters={SYNC_FIELD: base_key}, fields=fields)
    revisions = frappe.get_all(
        target_doctype,
        filters={SYNC_FIELD: ("like", f"{base_key}:R%")},
        fields=fields,
    )
    rows = exact + revisions
    rows.sort(key=lambda row: row.creation)
    return rows


def get_active_target(target_doctype: str, base_key: str) -> tuple[str | None, str | None]:
    meta = frappe.get_meta(target_doctype)
    if not meta.has_field(SYNC_FIELD):
        return None, None
    for row in _targets_for_base(target_doctype, base_key):
        if getattr(row, "docstatus", 0) != 2:
            return row.name, row.get(SYNC_FIELD)
    return None, None


def next_retriable_key(target_doctype: str, base_key: str) -> tuple[str, str | None]:
    active_name, active_key = get_active_target(target_doctype, base_key)
    if active_name:
        return active_key or base_key, active_name

    if not frappe.get_meta(target_doctype).has_field(SYNC_FIELD):
        return base_key, None
    revision = len(_targets_for_base(target_doctype, base_key)) + 1
    if revision == 1:
        return base_key, None
    candidate = f"{base_key}:R{revision}"
    if len(candidate) > MAX_SYNC_KEY_LENGTH:
        digest = hashlib.sha256(candidate.encode()).hexdigest()[:24]
        candidate = f"{base_key[:96]}:{digest}:R{revision}"
    return candidate, None

def create_document_once(
    *,
    base_key: str,
    operation: str,
    source_doctype: str,
    source_name: str,
    target_doctype: str,
    build_document: Callable[[], Any],
    payload: Any | None = None,
    ignore_permissions: bool = False,
) -> tuple[Any, bool]:
    """Create an ERPNext document exactly once per deterministic operation key.

    Returns ``(document, already_created)``. A cancelled target permits a numbered
    retry, while an active draft/submitted target is reused.
    """
    sync_key, active_target = next_retriable_key(target_doctype, base_key)
    if active_target:
        return frappe.get_doc(target_doctype, active_target), True

    existing_log = frappe.db.get_value(
        "Hotel ERP Sync Log",
        sync_key,
        ["status", "target_doctype", "target_name"],
        as_dict=True,
    )
    if existing_log:
        if existing_log.target_name and frappe.db.exists(existing_log.target_doctype, existing_log.target_name):
            return frappe.get_doc(existing_log.target_doctype, existing_log.target_name), True
        frappe.throw(
            _("Synchronization operation {0} is already in progress. Refresh before retrying.").format(sync_key)
        )

    try:
        log = frappe.get_doc(
            {
                "doctype": "Hotel ERP Sync Log",
                "idempotency_key": sync_key,
                "status": "In Progress",
                "operation": operation,
                "source_doctype": source_doctype,
                "source_name": source_name,
                "target_doctype": target_doctype,
                "payload_hash": payload_hash(payload) if payload is not None else None,
            }
        ).insert(ignore_permissions=True)
    except DuplicateEntryError:
        existing_log = frappe.db.get_value(
            "Hotel ERP Sync Log",
            sync_key,
            ["target_doctype", "target_name"],
            as_dict=True,
        )
        if existing_log and existing_log.target_name and frappe.db.exists(existing_log.target_doctype, existing_log.target_name):
            return frappe.get_doc(existing_log.target_doctype, existing_log.target_name), True
        frappe.throw(
            _("Another request is already processing synchronization key {0}.").format(sync_key)
        )

    target = build_document()
    if target.doctype != target_doctype:
        frappe.throw(_("Sync builder returned {0}; expected {1}.").format(target.doctype, target_doctype))
    if target.meta.has_field(SYNC_FIELD):
        target.set(SYNC_FIELD, sync_key)
    target.insert(ignore_permissions=ignore_permissions)

    log.db_set(
        {
            "status": "Completed",
            "target_name": target.name,
            "completed_at": now_datetime(),
        },
        update_modified=False,
    )
    return target, False
