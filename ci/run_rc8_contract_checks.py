from pathlib import Path
import ast
import json
import sys

root = Path(__file__).resolve().parents[1]
errors = []

if not any(token in (root / 'hotel_pms/__init__.py').read_text() for token in ('1.0.0rc8','1.0.0rc9')):
    errors.append('application version no longer includes RC8 contracts')

required = {
    'Hotel Distribution Connection', 'Hotel Distribution Room Mapping', 'Hotel Distribution Event',
    'Hotel Prearrival Form Template', 'Hotel Prearrival Form Question', 'Hotel Prearrival Form Submission',
}
found = {json.loads(path.read_text()).get('name') for path in root.glob('hotel_pms/hotel_pms/doctype/*/*.json')}
if required - found:
    errors.append(f'missing RC8 doctypes: {sorted(required-found)}')

for path in ('hotel_pms/distribution.py', 'hotel_pms/prearrival.py', 'hotel_pms/turnover.py'):
    text = (root / path).read_text()
    for forbidden in (
        '"doctype": "Sales Invoice"', '"doctype": "POS Invoice"', '"doctype": "Payment Entry"',
        '"doctype": "Journal Entry"', '"doctype": "Purchase Invoice"', '"doctype": "Stock Entry"',
    ):
        if forbidden in text:
            errors.append(f'{path} directly creates ERPNext financial/stock document: {forbidden}')

connection = (root / 'hotel_pms/hotel_pms/doctype/hotel_distribution_connection/hotel_distribution_connection.py').read_text()
for token in ('uncertified', 'cannot be marked Live', 'successful connection test'):
    if token.lower() not in connection.lower():
        errors.append(f'distribution connection governance missing: {token}')

rules = (root / 'hotel_pms/distribution_rules.py').read_text()
for token in ('def strict_overlap', 'def parse_ical_events', 'def validate_outbound_url', 'def snapshot_answers'):
    if token not in rules:
        errors.append(f'RC8 rule missing: {token}')

distribution = (root / 'hotel_pms/distribution.py').read_text()
for token in (
    'X-Hotel-Distribution-Signature', 'hmac.compare_digest', 'allow_redirects=False',
    'MAX_ICAL_BYTES', 'Ignored Duplicate', 'incoming_price_basis', 'authorized_source="Distribution"',
    '_enforce_public_feed_rate_limit', 'currency_needs_review', 'sync_interval_minutes',
):
    if token not in distribution:
        errors.append(f'distribution hardening missing: {token}')

prearrival = (root / 'hotel_pms/prearrival.py').read_text()
for token in ('max_uses=1', 'for update', 'snapshot_answers', 'answers_hash'):
    if token not in prearrival:
        errors.append(f'pre-arrival one-time contract missing: {token}')

hooks = (root / 'hotel_pms/hooks.py').read_text()
for token in ('hotel_pms.distribution.sync_all_ical_connections', 'hotel_pms.distribution.push_all_ari', 'hotel_pms.turnover.create_turnover_tasks'):
    if token not in hooks:
        errors.append(f'RC8 scheduler missing: {token}')

production_gate = (root / 'hotel_pms/production_gate.py').read_text()
for code in ('DISTRIBUTION_READINESS', 'PREARRIVAL_SECURITY', 'TURNOVER_READINESS'):
    if code not in production_gate:
        errors.append(f'Production Gate missing {code}')

registry = (root / 'hotel_pms/intelligence.py').read_text()
for key, maturity in (
    ('generic-ical-distribution', 'Shipped'), ('generic-json-distribution', 'Shipped'),
    ('channex-channel-adapter', 'Adapter'), ('staah-channel-adapter', 'Adapter'), ('aiosell-channel-adapter', 'Adapter'),
):
    start = registry.find(key)
    if start < 0 or f'"maturity_status": "{maturity}"' not in registry[start:start+700]:
        errors.append(f'integration registry maturity mismatch for {key}')


pyproject = (root / 'pyproject.toml').read_text()
for token in ('requires-python = ">=3.10"', 'frappe = ">=16.0.0,<17.0.0"', 'erpnext = ">=16.0.0,<17.0.0"'):
    if token not in pyproject:
        errors.append(f'Frappe Cloud compatibility declaration missing: {token}')

for path in ('hotel_pms/distribution.py','hotel_pms/prearrival.py','hotel_pms/turnover.py','hotel_pms/distribution_rules.py','hotel_pms/production_gate.py'):
    try:
        ast.parse((root / path).read_text())
    except Exception as exc:
        errors.append(f'{path}: {exc}')

print({'rc8_contract_errors': len(errors), 'rc8_doctypes': len(required)})
if errors:
    print('\n'.join(errors))
    sys.exit(1)
