from __future__ import annotations
import json,uuid
from functools import wraps
import frappe
from frappe import _
from frappe.utils import add_to_date,now_datetime
from hotel_pms.platform import assigned_properties,require_property,current_property
from hotel_pms.platform_rules import canonical_json,request_hash

class APIError(Exception):
 def __init__(self,code,message,status=400,details=None):self.code=code;self.message=message;self.status=status;self.details=details

def _request_id():return frappe.get_request_header('X-Request-ID') or str(uuid.uuid4())
def ok(data=None):return {'success':True,'request_id':_request_id(),'data':data}
def fail(code,message,details=None):
 frappe.local.response.http_status_code=400;return {'success':False,'request_id':_request_id(),'error':{'code':code,'message':message,'details':details}}
def _role_guard():
 roles=set(frappe.get_roles());
 if not roles.intersection({'System Manager','Hotel Manager','Hotel API User','Front Desk','Revenue Manager'}):raise APIError('FORBIDDEN','Hotel API role is required.',403)
def _idem_key(arg=None):return arg or frappe.get_request_header('X-Idempotency-Key')
def _with_idempotency(endpoint,payload,key,property=None,callback=None):
 if not key:return callback()
 user=frappe.session.user;raw=f'{user}::{endpoint}::{key}';full='API::'+__import__('hashlib').sha256(raw.encode()).hexdigest();h=request_hash(payload);existing=frappe.db.get_value('Hotel API Idempotency',full,['request_hash','status','response_json'],as_dict=True)
 if existing:
  if existing.request_hash!=h:raise APIError('IDEMPOTENCY_CONFLICT','The same idempotency key was used with a different request.',409)
  if existing.status=='Completed':return json.loads(existing.response_json)
  if existing.status=='Processing':raise APIError('REQUEST_IN_PROGRESS','The idempotent request is still processing.',409)
  frappe.db.set_value('Hotel API Idempotency',full,{'status':'Processing','error_code':None},update_modified=False)
 hours=int(frappe.db.get_single_value('Hotel PMS Settings','api_idempotency_hours') or 24)
 
 if not existing: frappe.get_doc({'doctype':'Hotel API Idempotency','key':full,'user':user,'endpoint':endpoint,'property':property,'request_hash':h,'status':'Processing','expires_at':add_to_date(now_datetime(),hours=hours)}).insert(ignore_permissions=True)
 try:
  result=callback();frappe.db.set_value('Hotel API Idempotency',full,{'status':'Completed','response_json':canonical_json(result)},update_modified=False);return result
 except Exception:
  frappe.db.set_value('Hotel API Idempotency',full,{'status':'Failed','error_code':'EXECUTION_ERROR'},update_modified=False);raise

def endpoint(fn):
 @wraps(fn)
 def wrapped(*args,**kwargs):
  try:_role_guard();return ok(fn(*args,**kwargs))
  except APIError as e:frappe.local.response.http_status_code=e.status;return {'success':False,'request_id':_request_id(),'error':{'code':e.code,'message':e.message,'details':e.details}}
  except frappe.PermissionError as e:frappe.local.response.http_status_code=403;return {'success':False,'request_id':_request_id(),'error':{'code':'FORBIDDEN','message':str(e)}}
  except Exception as e:frappe.log_error(frappe.get_traceback(),'Hotel API v1');frappe.local.response.http_status_code=400;return {'success':False,'request_id':_request_id(),'error':{'code':'VALIDATION_ERROR','message':str(e)}}
 return frappe.whitelist()(wrapped)

@endpoint
def properties():
 return {'items':frappe.get_all('Hotel Property',filters={'name':('in',assigned_properties())},fields=['name','property_name','company','timezone','check_in_time','check_out_time'])}

@endpoint
def availability(property,arrival_date,departure_date,room_type=None):
 require_property(property)
 from hotel_pms.hotel_pms.doctype.hotel_group_booking.hotel_group_booking import get_available_room_type_capacity
 room_types=[room_type] if room_type else frappe.get_all('Hotel Room Type',filters={'property':property,'enabled':1},pluck='name')
 return {'property':property,'arrival_date':arrival_date,'departure_date':departure_date,'room_types':[{'room_type':rt,'available':max(int(get_available_room_type_capacity(property,rt,arrival_date,departure_date)),0)} for rt in room_types]}

@endpoint
def reservation(name):
 doc=frappe.get_doc('Hotel Reservation',name);require_property(doc.property)
 return doc.as_dict()

@endpoint
def create_reservation(payload,idempotency_key=None):
 if isinstance(payload,str):payload=json.loads(payload)
 prop=payload.get('property') or current_property();require_property(prop,write=True);payload['property']=prop
 key=_idem_key(idempotency_key)
 if not key: raise APIError('IDEMPOTENCY_REQUIRED','X-Idempotency-Key is required for reservation creation.',400)
 payload['idempotency_key']=key
 def work():
  from hotel_pms.front_desk import quick_multi_room_booking
  return quick_multi_room_booking(payload)
 return _with_idempotency('create_reservation',payload,key,prop,work)

@endpoint
def room_status(property):
 require_property(property)
 return {'items':frappe.get_all('Hotel Room',filters={'property':property,'enabled':1},fields=['name','room_number','room_type','operational_status','housekeeping_status'],order_by='room_number asc')}

@endpoint
def health():
 from hotel_pms.platform import get_platform_dashboard
 return get_platform_dashboard()
