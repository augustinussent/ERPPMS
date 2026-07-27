from pathlib import Path
import ast, json, sys

root = Path(__file__).resolve().parents[1]
errors=[]
if '1.0.0rc9' not in (root/'hotel_pms/__init__.py').read_text(): errors.append('application version is not 1.0.0rc9')
required={
 'Hotel Kitchen Production Unit','Hotel Restaurant Printer Route','Hotel Restaurant Print Job',
 'Hotel Restaurant Table Cluster','Hotel Restaurant Table Cluster Member','Hotel Restaurant Alert',
}
found={json.loads(p.read_text()).get('name') for p in root.glob('hotel_pms/hotel_pms/doctype/*/*.json')}
if required-found: errors.append(f'missing RC9 doctypes: {sorted(required-found)}')
for path in ('hotel_pms/restaurant_controls.py','hotel_pms/restaurant_printing.py','hotel_pms/restaurant_controls_rules.py'):
 text=(root/path).read_text()
 for dt in ('Sales Invoice','POS Invoice','Payment Entry','Journal Entry','Purchase Invoice','Stock Entry'):
  if f'"doctype": "{dt}"' in text: errors.append(f'{path} creates forbidden {dt}')
 try: ast.parse(text)
 except Exception as exc: errors.append(f'{path}: {exc}')
platform=(root/'hotel_pms/platform.py').read_text()
for dt in ('Hotel Kitchen Production Unit','Hotel Restaurant Printer Route','Hotel Restaurant Print Job','Hotel Restaurant Table Cluster','Hotel Restaurant Alert'):
 if f"'{dt}':'property'" not in platform: errors.append(f'{dt} is not property scoped')
source=(root/'hotel_pms/restaurant_controls.py').read_text()
for token in ('for update','KOT-REV','action_bucket == "Add"','does not auto-reverse ERPNext stock','POS Opening Entry','POS Closing Entry'):
 if token not in source: errors.append(f'restaurant control missing {token}')
services=(root/'hotel_pms/services.py').read_text()
for token in ('require_restaurant_session','additional_discount_percentage','restaurant_prebill_context','queue_restaurant_print_jobs'):
 if token not in services: errors.append(f'services integration missing {token}')
fnb=(root/'hotel_pms/fnb_inventory.py').read_text()
if 'delta_action", "Add") != "Add"' not in fnb: errors.append('recipe posting is not limited to Add deltas')
gate=(root/'hotel_pms/production_gate.py').read_text()
for code in ('RESTAURANT_SESSION_CONTROL','KITCHEN_DELTA_CONTROL','RESTAURANT_PRINT_CONTROL'):
 if code not in gate: errors.append(f'production gate missing {code}')
print({'rc9_contract_errors':len(errors),'rc9_doctypes':len(required)})
if errors:
 print('\n'.join(errors)); sys.exit(1)
