from __future__ import annotations
import json
import frappe
from frappe import _
from frappe.utils import now_datetime
from hotel_pms.platform import require_property
from hotel_pms.sync import make_sync_key

def _loads(value,default=None):
 try:return json.loads(value) if value else (default if default is not None else {})
 except Exception:return default if default is not None else {}

@frappe.whitelist()
def create_session(company,property_name,abbreviation):
 key=make_sync_key('ONBOARD',company,abbreviation)
 existing=frappe.db.get_value('Hotel Onboarding Session',{'idempotency_key':key},'name')
 if existing:return frappe.get_doc('Hotel Onboarding Session',existing).as_dict()
 cfg={'company':company,'property_name':property_name,'abbreviation':abbreviation,'create_cost_center':True,'create_warehouse':True,'assign_current_user':True,'rooms':[],'room_types':[],'rate_plans':[],'outlets':[]}
 return frappe.get_doc({'doctype':'Hotel Onboarding Session','session_title':f'{property_name} Setup','company':company,'property_name':property_name,'abbreviation':abbreviation,'configuration_json':json.dumps(cfg,indent=2),'idempotency_key':key}).insert().as_dict()

@frappe.whitelist()
def get_session(session): return frappe.get_doc('Hotel Onboarding Session',session).as_dict()

@frappe.whitelist()
def scan_session(session):
 doc=frappe.get_doc('Hotel Onboarding Session',session);cfg=_loads(doc.configuration_json,{})
 checks={'company_exists':bool(frappe.db.exists('Company',doc.company)),'property_exists':bool(frappe.db.exists('Hotel Property',{'company':doc.company,'abbreviation':doc.abbreviation})),'cost_center':frappe.db.get_value('Cost Center',{'company':doc.company,'cost_center_name':doc.property_name},'name'),'warehouse':frappe.db.get_value('Warehouse',{'company':doc.company,'warehouse_name':doc.property_name},'name'),'settings_exists':bool(frappe.db.exists('Hotel PMS Settings','Hotel PMS Settings'))}
 doc.readiness_json=json.dumps(checks,indent=2,default=str);doc.status='Scanned';doc.current_step='Readiness scan';doc.save();return checks

@frappe.whitelist()
def plan_session(session):
 doc=frappe.get_doc('Hotel Onboarding Session',session);cfg=_loads(doc.configuration_json,{})
 if not frappe.db.exists('Company',doc.company):frappe.throw(_('Company does not exist.'))
 actions=[]
 prop=frappe.db.get_value('Hotel Property',{'company':doc.company,'abbreviation':doc.abbreviation},'name')
 actions.append({'step':'property','action':'reuse' if prop else 'create','target':prop or doc.property_name})
 for label,dt,filters in [('cost_center','Cost Center',{'company':doc.company,'cost_center_name':doc.property_name}),('warehouse','Warehouse',{'company':doc.company,'warehouse_name':doc.property_name})]: actions.append({'step':label,'action':'reuse' if frappe.db.exists(dt,filters) else 'create','target':doc.property_name})
 for collection,dt,keyfield in [('room_types','Hotel Room Type','room_type_name'),('rooms','Hotel Room','room_number'),('rate_plans','Hotel Rate Plan','rate_plan_name'),('outlets','Hotel Outlet','outlet_name')]:
  for row in cfg.get(collection,[]): actions.append({'step':collection,'action':'upsert','target':row.get(keyfield),'data':row})
 doc.plan_json=json.dumps(actions,indent=2,default=str);doc.status='Planned';doc.current_step='Plan ready';doc.save();return actions

def _ensure_cost_center(company,name):
 existing=frappe.db.get_value('Cost Center',{'company':company,'cost_center_name':name},'name')
 if existing:return existing
 parent=frappe.db.get_value('Cost Center',{'company':company,'is_group':1,'parent_cost_center':('is','not set')},'name') or frappe.db.get_value('Company',company,'cost_center')
 return frappe.get_doc({'doctype':'Cost Center','cost_center_name':name,'company':company,'parent_cost_center':parent,'is_group':0}).insert(ignore_permissions=True).name

def _ensure_warehouse(company,name):
 existing=frappe.db.get_value('Warehouse',{'company':company,'warehouse_name':name},'name')
 if existing:return existing
 return frappe.get_doc({'doctype':'Warehouse','warehouse_name':name,'company':company}).insert(ignore_permissions=True).name

@frappe.whitelist()
def apply_session(session):
 doc=frappe.get_doc('Hotel Onboarding Session',session);cfg=_loads(doc.configuration_json,{});actions=_loads(doc.plan_json,[])
 if not actions: actions=plan_session(session);doc.reload()
 applied=_loads(doc.applied_steps_json,[]);done={x.get('step_key') for x in applied};doc.status='Applying';doc.save()
 try:
  cc=_ensure_cost_center(doc.company,doc.property_name);wh=_ensure_warehouse(doc.company,doc.property_name)
  prop=frappe.db.get_value('Hotel Property',{'company':doc.company,'abbreviation':doc.abbreviation},'name')
  if not prop:
   p=frappe.get_doc({'doctype':'Hotel Property','property_name':doc.property_name,'company':doc.company,'abbreviation':doc.abbreviation,'enabled':1,'default_cost_center':cc,'default_warehouse':wh});p.insert(ignore_permissions=True);prop=p.name
  else: frappe.db.set_value('Hotel Property',prop,{'default_cost_center':cc,'default_warehouse':wh},update_modified=False)
  doc.property=prop
  if cfg.get('assign_current_user'):
   key=f'{frappe.session.user}::{prop}'
   if not frappe.db.exists('Hotel User Property Access',key):frappe.get_doc({'doctype':'Hotel User Property Access','user':frappe.session.user,'property':prop,'enabled':1,'is_default':1,'can_view_consolidated':1 if 'Hotel Manager' in frappe.get_roles() else 0,'access_level':'Manager','unique_key':key}).insert(ignore_permissions=True)
  specs=[('room_types','Hotel Room Type','room_type_name'),('rate_plans','Hotel Rate Plan','rate_plan_name'),('rooms','Hotel Room','room_number'),('outlets','Hotel Outlet','outlet_name')]
  for collection,dt,keyfield in specs:
   for row in cfg.get(collection,[]):
    data=dict(row);data['property']=prop
    if dt=='Hotel Outlet':data.setdefault('company',doc.company)
    filters={'property':prop,keyfield:data.get(keyfield)};name=frappe.db.get_value(dt,filters,'name')
    if name:
     target=frappe.get_doc(dt,name);target.update(data);target.save(ignore_permissions=True)
    else:frappe.get_doc({'doctype':dt,**data}).insert(ignore_permissions=True)
  applied.append({'step_key':'complete','at':str(now_datetime()),'property':prop});doc.applied_steps_json=json.dumps(applied,indent=2);doc.status='Completed';doc.current_step='Completed';doc.save();return doc.as_dict()
 except Exception:
  doc.status='Failed';doc.last_error=frappe.get_traceback();doc.save(ignore_permissions=True);raise

@frappe.whitelist()
def export_configuration(session):
 doc=frappe.get_doc('Hotel Onboarding Session',session);prop=doc.property
 if not prop:return _loads(doc.configuration_json,{})
 property_doc=frappe.get_doc('Hotel Property',prop).as_dict(no_nulls=True)
 safe={k:property_doc.get(k) for k in ('property_name','company','abbreviation','timezone','check_in_time','check_out_time','address','selling_price_list')}
 def rows(dt,fields):return frappe.get_all(dt,filters={'property':prop},fields=fields,order_by='creation asc')
 return {'schema_version':'0.9.0','property':safe,'room_types':rows('Hotel Room Type',['room_type_name','enabled','max_adults','max_children','housekeeping_minutes','base_rate','room_revenue_item']),'rooms':rows('Hotel Room',['room_number','room_type','floor','enabled','operational_status','housekeeping_status']),'rate_plans':rows('Hotel Rate Plan',['rate_plan_name','room_type','enabled','valid_from','valid_to','meal_plan','rate','min_stay','max_stay','refundable','base_rate_plan','derived_adjustment_type','derived_adjustment_value']),'outlets':rows('Hotel Outlet',['outlet_name','outlet_type','enabled','pos_profile','warehouse','cost_center','income_account'])}
