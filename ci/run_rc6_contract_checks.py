from pathlib import Path
import ast
import json
import sys

root = Path(__file__).resolve().parents[1]
errors = []

if '1.0.0rc6' not in (root / 'hotel_pms/__init__.py').read_text():
    errors.append('application version is not 1.0.0rc6')

required_doctypes = {
    'Hotel Intelligence Config', 'Hotel Intelligence Run', 'Hotel Intelligence Decision',
    'Hotel Night Audit Finding', 'Hotel Payment Correction', 'Hotel Integration Definition',
    'Hotel Integration Connection', 'Hotel Integration Go Live Check',
}
found = set()
for path in root.glob('hotel_pms/hotel_pms/doctype/*/*.json'):
    found.add(json.loads(path.read_text()).get('name'))
missing = required_doctypes - found
if missing:
    errors.append(f'missing RC6 doctypes: {sorted(missing)}')

module = (root / 'hotel_pms/intelligence.py').read_text()
for forbidden in (
    'frappe.new_doc("Sales Invoice")', 'frappe.new_doc("POS Invoice")',
    'frappe.new_doc("Payment Entry")', 'frappe.new_doc("Journal Entry")',
    'frappe.new_doc("Purchase Invoice")', 'frappe.new_doc("Stock Entry")',
    '"doctype": "Sales Invoice"', '"doctype": "POS Invoice"',
    '"doctype": "Payment Entry"', '"doctype": "Journal Entry"',
    '"doctype": "Purchase Invoice"', '"doctype": "Stock Entry"',
):
    if forbidden in module:
        errors.append(f'intelligence module directly creates financial/stock document: {forbidden}')
if 'create_refund_payment_entry' not in module:
    errors.append('payment correction does not reuse governed ERPNext refund path')
if 'financial_documents_created": 0' not in module:
    errors.append('night audit decision does not declare zero financial document creation')

hooks = (root / 'hotel_pms/hooks.py').read_text()
for doctype in required_doctypes - {'Hotel Integration Definition', 'Hotel Integration Go Live Check'}:
    if doctype not in hooks:
        errors.append(f'{doctype} missing property permission hook')
if 'hotel_pms.intelligence.run_scheduled_intelligence' not in hooks:
    errors.append('intelligence scheduler hook missing')

patches = (root / 'hotel_pms/patches.txt').read_text()
if 'hotel_pms.patches.v1_0_rc6.setup_intelligence' not in patches:
    errors.append('RC6 patch missing')

workflow = (root / '.github/workflows/ci.yml').read_text()
for token in ('run_rc6_contract_checks.py', 'test_intelligence_rc6_rules.py', 'run_rc6_bench_smoke.sh'):
    if token not in workflow:
        errors.append(f'CI missing {token}')

production_gate = (root / 'hotel_pms/production_gate.py').read_text()
for code in ('INTELLIGENCE_GOVERNANCE', 'PAYMENT_CORRECTION_CONTROL', 'INTEGRATION_READINESS'):
    if code not in production_gate:
        errors.append(f'Production Gate missing {code}')

print({'rc6_contract_errors': len(errors), 'rc6_doctypes': len(required_doctypes)})
if errors:
    print('\n'.join(errors))
    sys.exit(1)
