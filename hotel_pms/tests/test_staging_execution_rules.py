from hotel_pms.staging_execution_rules import (
    duplicate_active_keys,
    evidence_matches_environment,
    evidence_sha256,
    redact_payload,
    summarize_execution_checks,
)


def test_redaction_is_recursive_and_stable():
    payload = {"token": "abc", "nested": [{"api_secret": "x", "safe": 1}]}
    redacted = redact_payload(payload)
    assert redacted == {"token": "<REDACTED>", "nested": [{"api_secret": "<REDACTED>", "safe": 1}]}
    assert evidence_sha256(payload) == evidence_sha256(payload)
    assert "abc" not in str(redacted)


def test_required_execution_checks_cannot_disappear_silently():
    summary = summarize_execution_checks(
        [{"code": "A", "status": "Passed"}, {"code": "B", "status": "Warning"}],
        {"A", "B", "C"},
    )
    assert summary["status"] == "Failed"
    assert summary["missing_required"] == ["C"]


def test_evidence_must_match_exact_artifact_identity():
    env = {"release_version": "1.0.0rc5", "source_fingerprint": "abc", "image_digest": "sha256:1", "artifact_sha256": "def"}
    assert evidence_matches_environment(dict(env), env)
    changed = dict(env, image_digest="sha256:2")
    assert not evidence_matches_environment(changed, env)


def test_duplicate_active_sync_keys_ignore_cancelled_documents():
    rows = [
        {"sync_key": "A", "doctype": "Sales Invoice", "name": "SI-1", "docstatus": 1},
        {"sync_key": "A", "doctype": "Sales Invoice", "name": "SI-2", "docstatus": 0},
        {"sync_key": "B", "doctype": "Stock Entry", "name": "STE-1", "docstatus": 2},
        {"sync_key": "B", "doctype": "Stock Entry", "name": "STE-2", "docstatus": 1},
    ]
    duplicates = duplicate_active_keys(rows)
    assert len(duplicates) == 1
    assert duplicates[0]["sync_key"] == "A"
