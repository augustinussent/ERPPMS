from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1]
errors = []

version_text=(root / 'hotel_pms/__init__.py').read_text()
if not any(token in version_text for token in ('1.0.0rc5','1.0.0rc6')):
    errors.append('application version no longer includes RC5 staging-execution contracts')

production_gate = (root / 'hotel_pms/production_gate.py').read_text()
for code in ('STAGING_PREFLIGHT', 'SMOKE_REHEARSAL', 'RECON_SNAPSHOT', 'CUTOVER_BUNDLE'):
    if code not in production_gate:
        errors.append(f'production gate missing {code}')

validation = (root / 'hotel_pms/production_validation.py').read_text()
if '"Smoke"' not in validation:
    errors.append('Smoke rehearsal is not required by production validation')

rehearsal = json.loads((root / 'hotel_pms/hotel_pms/doctype/hotel_rehearsal_run/hotel_rehearsal_run.json').read_text())
run_type = next(row for row in rehearsal['fields'] if row['fieldname'] == 'run_type')
if 'Smoke' not in run_type.get('options', ''):
    errors.append('Hotel Rehearsal Run does not allow Smoke')

module = (root / 'hotel_pms/staging_execution.py').read_text()
for required in ('capture_staging_preflight', 'run_smoke_suite', 'capture_reconciliation_snapshot', 'build_cutover_bundle'):
    if f'def {required}' not in module:
        errors.append(f'staging execution missing {required}')
for forbidden in (
    '"doctype": "Sales Invoice"',
    '"doctype": "POS Invoice"',
    '"doctype": "Payment Entry"',
    '"doctype": "Journal Entry"',
    '"doctype": "Purchase Invoice"',
    '"doctype": "Stock Entry"',
):
    if forbidden in module:
        errors.append(f'staging execution must not create financial/stock document: {forbidden}')

for path in ('ci/run_staging_execution.sh', 'ci/build_evidence_manifest.py', 'ci/verify_staging_bundle.py'):
    if not (root / path).is_file():
        errors.append(f'missing RC5 execution tool: {path}')

patches = (root / 'hotel_pms/patches.txt').read_text()
if 'hotel_pms.patches.v1_0_rc5.setup_staging_execution' not in patches:
    errors.append('RC5 patch is missing')

workflow = (root / '.github/workflows/ci.yml').read_text()
if 'run_rc5_contract_checks.py' not in workflow or 'test_staging_execution_rules.py' not in workflow:
    errors.append('CI does not run RC5 contract and rule tests')

print({'rc5_contract_errors': len(errors)})
if errors:
    print('\n'.join(errors))
    sys.exit(1)
