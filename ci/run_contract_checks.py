from pathlib import Path
import ast,json,glob,sys
root=Path(__file__).resolve().parents[1];errors=[]
# field contract
for path in root.glob('hotel_pms/hotel_pms/doctype/*/*.json'):
 d=json.loads(path.read_text());names=[f.get('fieldname') for f in d.get('fields',[])];order=d.get('field_order',[])
 if len(names)!=len(set(names)):errors.append(f'{path}: duplicate fields')
 if set(names)!=set(order):errors.append(f'{path}: field_order mismatch')
# property scope coverage
hooks=ast.parse((root/'hotel_pms/hooks.py').read_text());scoped=set()
for node in hooks.body:
 if isinstance(node,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='permission_query_conditions' for x in node.targets):scoped={k.value for k in node.value.keys if isinstance(k,ast.Constant)}
shared={'Hotel PMS Settings','Hotel Guest Profile','Hotel Guest Blacklist','Hotel Guest Merge Request','Hotel Onboarding Session','Hotel System Health Snapshot','Hotel Backup Verification'}
for path in root.glob('hotel_pms/hotel_pms/doctype/*/*.json'):
 d=json.loads(path.read_text());
 if not d.get('istable') and d['name'] not in scoped and d['name'] not in shared:errors.append(f'{d["name"]}: missing property-scope declaration')
print({'scoped_doctypes':len(scoped),'errors':len(errors)})
if errors:print('\n'.join(errors));sys.exit(1)
