from __future__ import annotations
import csv,io,json
from pathlib import Path
import frappe
from frappe import _
from frappe.utils import getdate,now_datetime
from hotel_pms.platform import require_property
from hotel_pms.platform_rules import natural_key,normalize_email,normalize_phone

PRESETS={
 'Spreadsheet':{},
 'Generic PMS':{'guest name':'customer_name','email':'email','phone':'phone','room':'room_number','room type':'room_type_name','arrival':'arrival_date','departure':'departure_date','reservation id':'source_reference'},
 'eZee':{'guestname':'customer_name','guestemail':'email','guestmobile':'phone','roomno':'room_number','roomtype':'room_type_name','checkindate':'arrival_date','checkoutdate':'departure_date','bookingno':'source_reference'},
 'Cloudbeds':{'guest_name':'customer_name','guest_email':'email','guest_phone':'phone','room_name':'room_number','room_type_name':'room_type_name','start_date':'arrival_date','end_date':'departure_date','reservation_id':'source_reference'}
}

def _file_content(file_url):
 file_name=frappe.db.get_value('File',{'file_url':file_url},'name')
 if not file_name:frappe.throw(_('Source file was not found.'))
 return frappe.get_doc('File',file_name).get_content().decode('utf-8-sig')

def _mapping(batch,headers):
 custom=json.loads(batch.mapping_json or '{}');preset=PRESETS.get(batch.source_type,{})
 result={}
 for h in headers:
  result[h]=custom.get(h) or preset.get(h.strip().lower()) or h.strip().lower().replace(' ','_')
 return result

def _normalize(batch,row,mapping):
 data={mapping[k]:v.strip() if isinstance(v,str) else v for k,v in row.items() if mapping.get(k)};data['property']=batch.property
 if data.get('email'):data['email']=normalize_email(data['email'])
 if data.get('phone'):data['phone']=normalize_phone(data['phone'])
 for f in ('arrival_date','departure_date','stay_date'):
  if data.get(f):data[f]=str(getdate(data[f]))
 return data

def _plan(batch,data):
 e=batch.entity_type; key=natural_key(e,data); action='Insert';target_dt=None;target=None;error=None
 if e=='Customer':
  target_dt='Customer';target=(frappe.db.get_value('Customer',{'email_id':data.get('email')},'name') if data.get('email') and frappe.get_meta('Customer').has_field('email_id') else None) or (frappe.db.get_value('Customer',{'mobile_no':data.get('phone')},'name') if data.get('phone') and frappe.get_meta('Customer').has_field('mobile_no') else None)
  if target: action='Skip'
  elif not data.get('customer_name'):action,error='Reject','customer_name is required'
 elif e=='Room Type':
  target_dt='Hotel Room Type';target=frappe.db.get_value(target_dt,{'property':batch.property,'room_type_name':data.get('room_type_name')},'name');action='Update' if target and batch.allow_updates else ('Skip' if target else 'Insert')
  if not data.get('room_type_name') or not data.get('room_revenue_item'):action,error='Reject','room_type_name and room_revenue_item are required'
 elif e=='Room':
  target_dt='Hotel Room';target=frappe.db.get_value(target_dt,{'property':batch.property,'room_number':data.get('room_number')},'name');action='Update' if target and batch.allow_updates else ('Skip' if target else 'Insert')
  if not data.get('room_number') or not data.get('room_type'):action,error='Reject','room_number and room_type are required'
 elif e=='Reservation':
  target_dt='Hotel Reservation';target=frappe.db.get_value(target_dt,{'external_reference':data.get('source_reference')},'name') if data.get('source_reference') and frappe.get_meta(target_dt).has_field('external_reference') else None;action='Skip' if target else 'Insert'
  for req in ('customer','arrival_date','departure_date','room_type'):
   if not data.get(req):action,error='Reject',f'{req} is required';break
 elif e=='Rate Calendar':
  target_dt='Hotel Rate Calendar';data['rate_date']=data.pop('stay_date',data.get('rate_date'));filters={k:data.get(k) for k in ('property','rate_plan','room_type','rate_date')};target=frappe.db.get_value(target_dt,filters,'name');action='Update' if target and batch.allow_updates else ('Skip' if target else 'Insert')
 elif e=='Deposit Review': target_dt='Payment Entry';action='Review';error='Accounting deposits require manual verification and are never auto-posted.'
 return key,action,target_dt,target,error

@frappe.whitelist()
def dry_run_batch(batch):
 b=frappe.get_doc('Hotel Migration Batch',batch);require_property(b.property,write=True)
 max_rows=int(frappe.db.get_single_value('Hotel PMS Settings','migration_max_rows') or 10000)
 text=_file_content(b.source_file);reader=csv.DictReader(io.StringIO(text));mapping=_mapping(b,reader.fieldnames or [])
 frappe.db.delete('Hotel Migration Row',{'batch':b.name});counts={'Insert':0,'Update':0,'Skip':0,'Reject':0,'Review':0};total=0
 for idx,row in enumerate(reader,1):
  if idx>max_rows:frappe.throw(_('CSV exceeds the configured maximum of {0} rows.').format(max_rows))
  data=_normalize(b,row,mapping);key,action,dt,target,error=_plan(b,data);counts[action]+=1;total+=1
  frappe.get_doc({'doctype':'Hotel Migration Row','batch':b.name,'property':b.property,'row_number':idx,'entity_type':b.entity_type,'source_key':key,'action':action,'target_doctype':dt,'target_name':target,'status':'Rejected' if action=='Reject' else 'Planned','data_json':json.dumps(data,default=str),'error_message':error,'unique_key':f'{b.name}::{idx}'}).insert(ignore_permissions=True)
 b.db_set({'status':'Dry Run Complete','total_rows':total,'insert_count':counts['Insert'],'update_count':counts['Update'],'skip_count':counts['Skip'],'reject_count':counts['Reject'],'dry_run_summary':json.dumps({'counts':counts,'mapping':mapping},indent=2)},update_modified=True)
 return get_batch_summary(b.name)

def _import_row(row,b):
 data=json.loads(row.data_json or '{}');e=b.entity_type
 if row.action in ('Skip','Reject','Review'):return None
 if e=='Customer':
  customer=frappe.get_doc({'doctype':'Customer','customer_name':data['customer_name'],'customer_type':'Individual','customer_group':data.get('customer_group') or frappe.db.get_value('Customer Group',{'is_group':0},'name'),'territory':data.get('territory') or frappe.db.get_value('Territory',{'is_group':0},'name')}).insert(ignore_permissions=True)
  if data.get('email') or data.get('phone'):
   contact=frappe.get_doc({'doctype':'Contact','first_name':data['customer_name'],'email_ids':[{'email_id':data.get('email'),'is_primary':1}] if data.get('email') else [],'phone_nos':[{'phone':data.get('phone'),'is_primary_phone':1}] if data.get('phone') else [],'links':[{'link_doctype':'Customer','link_name':customer.name}]}).insert(ignore_permissions=True)
  return customer.name
 if e=='Room Type':
  payload={'doctype':'Hotel Room Type','property':b.property,'enabled':1,'max_adults':2,'max_children':0,**data};name=row.target_name
 elif e=='Room':payload={'doctype':'Hotel Room','property':b.property,'enabled':1,'operational_status':'Available','housekeeping_status':'Clean',**data};name=row.target_name
 elif e=='Rate Calendar':payload={'doctype':'Hotel Rate Calendar',**data};name=row.target_name
 elif e=='Reservation':
  payload={'doctype':'Hotel Reservation','property':b.property,'guest':data['customer'],'billing_customer':data.get('billing_customer') or data['customer'],'arrival_date':data['arrival_date'],'departure_date':data['departure_date'],'status':'Tentative','source':'Direct','source_reference':data.get('source_reference'),'rooms':[{'room_type':data['room_type'],'rate_plan':data.get('rate_plan'),'nightly_rate':data.get('nightly_rate') or 0}]};name=None
 else:return None
 if name:
  doc=frappe.get_doc(payload['doctype'],name);doc.update({k:v for k,v in payload.items() if k!='doctype'});doc.save(ignore_permissions=True)
 else:doc=frappe.get_doc(payload).insert(ignore_permissions=True)
 return doc.name

@frappe.whitelist()
def commit_batch(batch):
 b=frappe.get_doc('Hotel Migration Batch',batch);require_property(b.property,write=True)
 if b.status!='Dry Run Complete':frappe.throw(_('Run dry-run before commit.'))
 b.db_set({'status':'Importing','started_at':now_datetime()},update_modified=True);errors=[];done=0
 for row_name in frappe.get_all('Hotel Migration Row',filters={'batch':b.name},order_by='row_number asc',pluck='name'):
  row=frappe.get_doc('Hotel Migration Row',row_name)
  try:
   target=_import_row(row,b)
   if target:row.db_set({'target_name':target,'status':'Imported'},update_modified=False);done+=1
  except Exception as exc:row.db_set({'status':'Failed','error_message':str(exc)[:500]},update_modified=False);errors.append({'row':row.row_number,'error':str(exc)})
 status='Completed with Errors' if errors else 'Completed';b.db_set({'status':status,'completed_at':now_datetime(),'import_summary':json.dumps({'imported':done,'errors':errors},indent=2)},update_modified=True);return get_batch_summary(b.name)

@frappe.whitelist()
def rollback_batch(batch):
 b=frappe.get_doc('Hotel Migration Batch',batch);require_property(b.property,write=True);rolled=[];errors=[]
 safe={'Hotel Room','Hotel Room Type','Hotel Rate Calendar','Customer','Hotel Reservation'}
 rows=frappe.get_all('Hotel Migration Row',filters={'batch':b.name,'status':'Imported'},fields=['name','target_doctype','target_name'],order_by='row_number desc')
 for r in rows:
  try:
   if r.target_doctype not in safe:continue
   doc=frappe.get_doc(r.target_doctype,r.target_name)
   if doc.docstatus!=0:raise Exception('Submitted documents cannot be rolled back automatically.')
   doc.delete(ignore_permissions=True);frappe.db.set_value('Hotel Migration Row',r.name,'status','Rolled Back',update_modified=False);rolled.append(r.target_name)
  except Exception as exc:errors.append({'target':r.target_name,'error':str(exc)})
 b.db_set('status','Rolled Back' if not errors else 'Completed with Errors');return {'rolled_back':rolled,'errors':errors}

@frappe.whitelist()
def get_batch_summary(batch):
 b=frappe.get_doc('Hotel Migration Batch',batch);require_property(b.property)
 return {'batch':b.as_dict(),'rows':frappe.get_all('Hotel Migration Row',filters={'batch':b.name},fields=['row_number','source_key','action','status','target_doctype','target_name','error_message'],order_by='row_number asc',limit=200)}
