from pathlib import Path
import ast
import sys

root = Path(__file__).resolve().parents[1]
errors = []

version_text = (root / "hotel_pms/__init__.py").read_text()
if not any(token in version_text for token in ('1.0.0rc7', '1.0.0rc8', '1.0.0rc9')):
    errors.append("application version is not 1.0.0rc7")

rules = (root / "hotel_pms/intelligence_rules.py").read_text()
for token in (
    'maximum_refundable = min(original, refundable)',
    'def integration_readiness_reasons',
    'Connection health status is Failed.',
):
    if token not in rules:
        errors.append(f"RC7 rule missing: {token}")

integration = (root / "hotel_pms/intelligence.py").read_text()
if 'previous_status if previous_status in ("Ready", "Live") else "Tested"' not in integration:
    errors.append("successful integration test does not preserve Ready/Live status")
if '"Purchase Invoice": ("custom_hotel_sync_key",)' not in integration:
    errors.append("ERPNext integration health test does not verify Purchase Invoice sync key")

controller = (root / "hotel_pms/hotel_pms/doctype/hotel_integration_connection/hotel_integration_connection.py").read_text()
for token in (
    'if self.status in ("Ready", "Live")',
    'A successful Test Connection result is required',
    'Ready or Live integrations must be enabled',
):
    if token not in controller:
        errors.append(f"integration connection validation missing: {token}")

correction = (root / "hotel_pms/hotel_pms/doctype/hotel_payment_correction/hotel_payment_correction.py").read_text()
if 'self.refundable_amount=float(plan.get("maximum_refundable") or 0)' not in correction:
    errors.append("payment correction does not persist capped refundable amount")

production_gate = (root / "hotel_pms/production_gate.py").read_text()
for token in (
    '"Pending Approval"',
    '"Approved"',
    '"Failed"',
    'filters={"property":property_name,"enabled":1}',
    'integration_readiness_reasons(',
):
    if token not in production_gate:
        errors.append(f"RC7 Production Gate contract missing: {token}")

parallel = (root / "ci/run_parallel_reconciliation.py").read_text()
if 'input_errors' not in parallel or 'legacy_value, pms_value and tolerance must be numeric' not in parallel:
    errors.append("parallel-run validator still accepts empty/non-numeric values")

for path in (
    "hotel_pms/tests/test_intelligence_rc7_rules.py",
    "hotel_pms/tests/test_intelligence_rc7_integration.py",
    "ci/run_rc7_bench_smoke.sh",
):
    if not (root / path).is_file():
        errors.append(f"missing RC7 validation file: {path}")

# Parse patched executable files explicitly.
for path in (
    "hotel_pms/intelligence.py",
    "hotel_pms/intelligence_rules.py",
    "hotel_pms/production_gate.py",
    "hotel_pms/hotel_pms/doctype/hotel_integration_connection/hotel_integration_connection.py",
    "hotel_pms/hotel_pms/doctype/hotel_payment_correction/hotel_payment_correction.py",
    "ci/run_parallel_reconciliation.py",
):
    try:
        ast.parse((root / path).read_text())
    except Exception as exc:
        errors.append(f"{path}: {exc}")

print({"rc7_contract_errors": len(errors)})
if errors:
    print("\n".join(errors))
    sys.exit(1)
