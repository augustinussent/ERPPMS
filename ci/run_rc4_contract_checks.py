from pathlib import Path
import ast
import json
import re
import sys

root = Path(__file__).resolve().parents[1]
errors = []

required_doctypes = {
    "Hotel Release Manifest",
    "Hotel Rehearsal Run",
    "Hotel Parallel Run Batch",
    "Hotel Parallel Run Row",
    "Hotel Validation Evidence",
}
found = set()
for path in root.glob("hotel_pms/hotel_pms/doctype/*/*.json"):
    try:
        found.add(json.loads(path.read_text())["name"])
    except Exception as exc:
        errors.append(f"{path}: {exc}")
for doctype in sorted(required_doctypes - found):
    errors.append(f"missing RC4 doctype: {doctype}")

version = (root / "hotel_pms/__init__.py").read_text()
if '1.0.0rc' not in version and '1.0.0"' not in version:
    errors.append("application version no longer belongs to the v1.0 release line")

production_gate = (root / "hotel_pms/production_gate.py").read_text()
for code in (
    "MANIFEST_INTEGRITY",
    "BLANK_INSTALL_REHEARSAL",
    "UPGRADE_REHEARSAL",
    "CONCURRENCY_REHEARSAL",
    "SECURITY_REHEARSAL",
    "RESTORE_REHEARSAL",
    "ROLLBACK_REHEARSAL",
    "PERFORMANCE_REHEARSAL",
    "PARALLEL_RECON",
):
    if code not in production_gate:
        errors.append(f"production gate is missing {code}")

validation = (root / "hotel_pms/production_validation.py").read_text()
for forbidden in (
    '"doctype": "Sales Invoice"',
    '"doctype": "POS Invoice"',
    '"doctype": "Payment Entry"',
    '"doctype": "Journal Entry"',
    '"doctype": "Purchase Invoice"',
    '"doctype": "Stock Entry"',
):
    if forbidden in validation:
        errors.append(f"production validation must not create financial/stock document: {forbidden}")

manifest = json.loads((root / "hotel_pms/hotel_pms/doctype/hotel_release_manifest/hotel_release_manifest.json").read_text())
for field in ("promotion_target_version", "source_fingerprint", "artifact_sha256", "image_digest", "promoted_artifact_sha256", "promoted_image_digest", "gate_run"):
    if field not in {row["fieldname"] for row in manifest["fields"]}:
        errors.append(f"release manifest missing field {field}")

gate = json.loads((root / "hotel_pms/hotel_pms/doctype/hotel_production_gate_run/hotel_production_gate_run.json").read_text())
for field in ("release_manifest", "expected_source_fingerprint", "actual_source_fingerprint", "expected_artifact_sha256", "actual_artifact_sha256", "promotion_status", "promoted_at", "promoted_by"):
    if field not in {row["fieldname"] for row in gate["fields"]}:
        errors.append(f"production gate missing field {field}")

patches = (root / "hotel_pms/patches.txt").read_text()
if "hotel_pms.patches.v1_0_rc4.setup_production_validation" not in patches:
    errors.append("RC4 setup patch is missing")

workflow = (root / ".github/workflows/ci.yml").read_text()
if "run_rc4_contract_checks.py" not in workflow or "test_production_validation_rules.py" not in workflow:
    errors.append("CI does not run RC4 contract and rule tests")

platform = (root / "hotel_pms/platform.py").read_text()
for doctype in ("Hotel Rehearsal Run","Hotel Parallel Run Batch","Hotel Validation Evidence"):
    if f"'{doctype}':'property'" not in platform:
        errors.append(f"platform property map is missing {doctype}")

rules = (root / "hotel_pms/production_validation_rules.py").read_text()
if "<PROMOTION_VERSION>" not in rules:
    errors.append("normalized promotion fingerprint is missing")

print({"rc4_contract_errors": len(errors), "required_doctypes": len(required_doctypes)})
if errors:
    print("\n".join(errors))
    sys.exit(1)
