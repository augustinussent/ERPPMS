from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

SENSITIVE_MARKERS = (
    "secret",
    "password",
    "token",
    "api_key",
    "api_secret",
    "encryption_key",
    "access_key",
    "private_key",
)


def is_sensitive_key(key: object) -> bool:
    normalized = str(key or "").strip().lower()
    return any(marker in normalized for marker in SENSITIVE_MARKERS)


def redact_payload(value):
    """Return a JSON-safe copy with secret-like values removed.

    Evidence bundles must prove configuration presence without becoming a
    convenient archive of production credentials.
    """
    if isinstance(value, Mapping):
        return {
            str(key): "<REDACTED>" if is_sensitive_key(key) else redact_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_payload(item) for item in value]
    return value


def canonical_json(value) -> str:
    return json.dumps(redact_payload(value), sort_keys=True, separators=(",", ":"), default=str)


def evidence_sha256(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def summarize_execution_checks(checks: list[dict], required_codes: set[str] | None = None) -> dict:
    required_codes = set(required_codes or ())
    seen = {str(row.get("code") or "") for row in checks}
    missing = sorted(required_codes - seen)
    failed = [row for row in checks if row.get("status") == "Failed"]
    warnings = [row for row in checks if row.get("status") == "Warning"]
    status = "Failed" if failed or missing else ("Warning" if warnings else "Passed")
    return {
        "status": status,
        "total": len(checks),
        "passed": sum(row.get("status") == "Passed" for row in checks),
        "warnings": len(warnings),
        "failed": len(failed),
        "missing_required": missing,
    }


def evidence_matches_environment(metadata: dict | None, environment: dict | None) -> bool:
    metadata = metadata or {}
    environment = environment or {}
    for field in ("release_version", "source_fingerprint", "image_digest", "artifact_sha256"):
        expected = environment.get(field)
        if expected and metadata.get(field) != expected:
            return False
    return True


def duplicate_active_keys(rows: list[dict]) -> list[dict]:
    """Return only sync keys represented by more than one active document."""
    by_key: dict[str, list[dict]] = {}
    for row in rows:
        key = str(row.get("sync_key") or "").strip()
        if not key or int(row.get("docstatus") or 0) == 2:
            continue
        by_key.setdefault(key, []).append(row)
    return [
        {"sync_key": key, "documents": documents, "count": len(documents)}
        for key, documents in sorted(by_key.items())
        if len(documents) > 1
    ]
