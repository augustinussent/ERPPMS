from __future__ import annotations
import hashlib, json, os, shutil
from datetime import datetime
from pathlib import Path
import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, now_datetime, get_datetime

PROPERTY_DOCTYPES={
 'Hotel Cancellation':'property','Hotel Cancellation Policy':'property','Hotel Folio Transfer':'property','Hotel Property':'name','Hotel User Property Access':'property','Hotel ERP Sync Log':'property','Hotel Guest Access Token':'property','Hotel Guest Action Log':'property','Hotel Guest Consent':'property','Hotel Guest Privacy Request':'property','Hotel Voucher Redemption':'property','Hotel Reservation':'property','Hotel Room':'property','Hotel Room Type':'property','Hotel Folio':'property','Hotel Group Booking':'property','Hotel Group Folio':'property','Hotel Banquet Event Order':'property','Hotel Function Space':'property','Hotel Package Template':'property','Hotel Package Posting':'@group_booking','Hotel Rate Plan':'property','Hotel Rate Season':'property','Hotel Rate Calendar':'property','Hotel Rate Approval':'property','Hotel Voucher':'property','Hotel Travel Agent Contract':'property','Hotel Travel Agent Settlement':'property','Hotel Tax Profile':'property','Hotel City Ledger Account':'property','Hotel City Ledger Folio':'property','Hotel Direct Bill Approval':'@reservation','Hotel Cashier Shift':'property','Hotel Cashier Movement':'@cashier_shift','Hotel Housekeeping Task':'property','Hotel Room Inspection':'property','Hotel Lost and Found':'property','Hotel Maintenance Ticket':'property','Hotel Preventive Maintenance Schedule':'property','Hotel Room Status Log':'property','Hotel SOP Candidate':'property','Hotel Cleaning Checklist Template':'property','Hotel Stay Change Log':'property','Hotel Guest Registration':'property','Hotel Outlet':'property','Hotel Dining Area':'@outlet','Hotel Restaurant Table':'@outlet','Hotel Table Reservation':'@outlet','Hotel Outlet Menu Item':'@outlet','Hotel Restaurant Order':'property','Hotel Restaurant Bill Split':'@restaurant_order','Hotel Kitchen Ticket':'property','Hotel Laundry Rate':'property','Hotel Laundry Order':'property','Hotel Guest Experience':'property','Hotel Experience Booking':'property','Hotel Shift Handover':'property','Hotel Guest Property Note':'property','Hotel Migration Batch':'property','Hotel Migration Row':'property','Hotel Webhook Subscription':'property','Hotel Webhook Delivery':'property','Hotel API Idempotency':'property','Hotel Production Gate Run':'property'
}
RELATION_SQL={
 'Hotel Package Posting':("Hotel Group Booking","group_booking"), 'Hotel Direct Bill Approval':("Hotel Reservation","reservation"), 'Hotel Cashier Movement':("Hotel Cashier Shift","cashier_shift"),
 'Hotel Dining Area':("Hotel Outlet","outlet"),'Hotel Restaurant Table':("Hotel Outlet","outlet"),'Hotel Table Reservation':("Hotel Outlet","outlet"),'Hotel Outlet Menu Item':("Hotel Outlet","outlet"),'Hotel Restaurant Bill Split':("Hotel Restaurant Order","restaurant_order")
}

def is_privileged(user=None):
 user=user or frappe.session.user
 return user=='Administrator' or 'System Manager' in frappe.get_roles(user)

def assigned_properties(user=None,include_disabled=False):
 user=user or frappe.session.user
 if is_privileged(user): return frappe.get_all('Hotel Property',filters={} if include_disabled else {'enabled':1},pluck='name')
 filters={'user':user,'enabled':1}
 return frappe.get_all('Hotel User Property Access',filters=filters,pluck='property')

def require_property(property_name,user=None,write=False):
 user=user or frappe.session.user
 if is_privileged(user): return property_name
 if not property_name or property_name not in assigned_properties(user): frappe.throw(_('You are not assigned to property {0}.').format(property_name or '-'),frappe.PermissionError)
 if write:
  level=frappe.db.get_value('Hotel User Property Access',{'user':user,'property':property_name,'enabled':1},'access_level')
  if level=='Read Only': frappe.throw(_('Property access is read-only.'),frappe.PermissionError)
 return property_name

def current_property(user=None):
 user=user or frappe.session.user; allowed=assigned_properties(user)
 selected=frappe.defaults.get_user_default('hotel_pms_current_property',user)
 if selected in allowed:return selected
 default=frappe.db.get_value('Hotel User Property Access',{'user':user,'enabled':1,'is_default':1},'property')
 return default if default in allowed else (allowed[0] if allowed else None)

@frappe.whitelist()
def set_current_property(property_name):
 require_property(property_name); frappe.defaults.set_user_default('hotel_pms_current_property',property_name); return {'property':property_name}

@frappe.whitelist()
def get_property_scope():
 props=assigned_properties(); return {'properties':props,'current_property':current_property(),'can_consolidate':can_view_consolidated()}

def can_view_consolidated(user=None):
 user=user or frappe.session.user
 if is_privileged(user) or 'Hotel Cross Property Manager' in frappe.get_roles(user): return True
 return bool(frappe.db.exists('Hotel User Property Access',{'user':user,'enabled':1,'can_view_consolidated':1}))

def extend_bootinfo(bootinfo):
 try: bootinfo.hotel_pms_property_scope=get_property_scope()
 except Exception: bootinfo.hotel_pms_property_scope={'properties':[],'current_property':None,'can_consolidate':False}

def _property_expr(doctype):
 table=f"`tab{doctype}`"; field=PROPERTY_DOCTYPES.get(doctype)
 if field=='name': return f"{table}.name"
 if field and not field.startswith('@'): return f"{table}.`{field}`"
 rel=RELATION_SQL.get(doctype)
 if rel:
  target,link=rel; return f"(select p.property from `tab{target}` p where p.name={table}.`{link}`)"
 return None

def permission_query(doctype,user=None):
 user=user or frappe.session.user
 if is_privileged(user): return ''
 props=assigned_properties(user)
 if not props:return '1=0'
 expr=_property_expr(doctype)
 if not expr:return '1=0'
 escaped=', '.join(frappe.db.escape(x) for x in props)
 return f"{expr} in ({escaped})"

def document_has_permission(doc,user=None,permission_type=None):
 user=user or frappe.session.user
 if is_privileged(user):return True
 doctype=doc.doctype; field=PROPERTY_DOCTYPES.get(doctype)
 prop=None
 if field=='name': prop=doc.name
 elif field and not field.startswith('@'): prop=doc.get(field)
 elif doctype in RELATION_SQL:
  target,link=RELATION_SQL[doctype]; linked=doc.get(link); prop=frappe.db.get_value(target,linked,'property') if linked else None
 if not prop:return False
 if prop not in assigned_properties(user):return False
 if permission_type in ('write','create','delete','submit','cancel'):
  level=frappe.db.get_value('Hotel User Property Access',{'user':user,'property':prop,'enabled':1},'access_level')
  return level!='Read Only'
 return True

def query_condition_factory(doctype): return lambda user=None: permission_query(doctype,user)
def has_permission_factory(doc,user=None,permission_type=None): return document_has_permission(doc,user,permission_type)

@frappe.whitelist()
def get_platform_dashboard(property=None):
 if property: require_property(property)
 health=frappe.get_all('Hotel System Health Snapshot',fields=['captured_at','overall_status','disk_used_percent','backup_age_hours','failed_sync_count','dead_webhook_count'],order_by='captured_at desc',limit=1)
 wh_filters={'status':'Dead Letter'}
 if property: wh_filters['property']=property
 dead=frappe.get_all('Hotel Webhook Delivery',filters=wh_filters,fields=['name','event_name','attempts','last_error'],order_by='modified desc',limit=10)
 assigned=assigned_properties()
 scope=[property] if property else assigned
 if not property and len(scope)>1 and not can_view_consolidated(): scope=[current_property()] if current_property() else []
 metrics=_consolidated_metrics(scope)
 storage=get_storage_report();access=get_access_review();privacy=frappe.db.count('Hotel Guest Profile',{'privacy_status':'Pending Anonymization'})
 cards={'Assigned properties':len(assigned),'Rooms':metrics['rooms'],'Occupied':metrics['occupied'],'Month revenue':metrics['month_revenue'],'Open service issues':metrics['open_service_issues'],'Dead webhooks':frappe.db.count('Hotel Webhook Delivery',wh_filters),'Failed sync':frappe.db.count('Hotel ERP Sync Log',{'status':'Failed'}),'Storage GB':storage['total_gb'],'Users missing property':access['users_missing_property'],'Privacy review due':privacy}
 return {'cards':cards,'metrics_by_property':metrics['by_property'],'storage':storage,'access_review':access,'health':health[0] if health else {},'dead_webhooks':dead}

def _consolidated_metrics(properties):
 result={'rooms':0,'occupied':0,'month_revenue':0.0,'open_service_issues':0,'by_property':[]}
 if not properties:return result
 month_start=now_datetime().replace(day=1,hour=0,minute=0,second=0,microsecond=0)
 for prop in properties:
  rooms=frappe.db.count('Hotel Room',{'property':prop,'enabled':1});occupied=frappe.db.count('Hotel Room',{'property':prop,'operational_status':'Occupied'})
  revenue=frappe.db.sql("""select coalesce(sum(si.base_grand_total),0) from `tabSales Invoice` si inner join `tabHotel Reservation` r on r.name=si.custom_hotel_reservation where si.docstatus=1 and r.property=%s and si.posting_date>=%s""",(prop,month_start.date()))[0][0] if frappe.get_meta('Sales Invoice').has_field('custom_hotel_reservation') else 0
  issues=frappe.db.count('Hotel Maintenance Ticket',{'property':prop,'status':('not in',['Resolved','Closed','Cancelled'])})
  row={'property':prop,'rooms':rooms,'occupied':occupied,'month_revenue':float(revenue or 0),'open_service_issues':issues};result['by_property'].append(row)
  for k in ('rooms','occupied','open_service_issues'):result[k]+=row[k]
  result['month_revenue']+=row['month_revenue']
 return result

def _backup_files():
 site=Path(frappe.get_site_path()); backup_dir=site/'private'/'backups'
 if not backup_dir.exists():return []
 candidates=[p for p in backup_dir.iterdir() if p.is_file() and ('database' in p.name or p.name.endswith('.sql.gz') or p.name.endswith('.sql'))]
 return sorted(candidates,key=lambda p:p.stat().st_mtime,reverse=True)

def capture_health_snapshot():
 now=now_datetime(); settings=frappe.get_single('Hotel PMS Settings')
 details={}; overall='Healthy'; db_status='OK'
 try: frappe.db.sql('select 1')
 except Exception as e: db_status=f'ERROR: {e}';overall='Critical'
 usage=shutil.disk_usage(frappe.get_site_path()); used=round((usage.used/usage.total)*100,2); free=round(usage.free/(1024**3),2)
 warning=flt(settings.get('disk_warning_percent') or 80); critical=flt(settings.get('disk_critical_percent') or 90)
 if used>=critical:overall='Critical'
 elif used>=warning and overall!='Critical':overall='Warning'
 backups=_backup_files(); latest_dt=None; age=None
 if backups:
  latest_dt=get_datetime(datetime.fromtimestamp(backups[0].stat().st_mtime)); age=(now-latest_dt).total_seconds()/3600
 threshold=flt(settings.get('backup_freshness_hours') or 24)
 if age is None or age>threshold: overall='Critical' if age is None else ('Warning' if overall=='Healthy' else overall)
 failed_sync=frappe.db.count('Hotel ERP Sync Log',{'status':('in',['Failed','In Progress'])})
 dead=frappe.db.count('Hotel Webhook Delivery',{'status':'Dead Letter'})
 errors=frappe.db.count('Error Log',{'creation':('>=',add_to_date(now,hours=-24))})
 if failed_sync or dead: overall='Warning' if overall=='Healthy' else overall
 heartbeat=settings.get('last_worker_heartbeat');heartbeat_age=(now-get_datetime(heartbeat)).total_seconds()/60 if heartbeat else None;scheduler='Paused' if cint(getattr(frappe.conf,'pause_scheduler',0)) else ('Healthy' if heartbeat_age is not None and heartbeat_age<15 else 'Stale')
 if scheduler!='Healthy': overall='Critical' if scheduler=='Paused' else ('Warning' if overall=='Healthy' else overall)
 queue_status='Unknown'
 try:
  queue_status=str(frappe.db.count('RQ Job',{'status':('in',['queued','started','failed'])}))
 except Exception: pass
 doc=frappe.get_doc({'doctype':'Hotel System Health Snapshot','captured_at':now,'overall_status':overall,'database_status':db_status,'scheduler_status':scheduler,'queue_status':queue_status,'websocket_status':'External probe required','disk_used_percent':used,'disk_free_gb':free,'latest_backup_at':latest_dt,'backup_age_hours':age,'failed_sync_count':failed_sync,'dead_webhook_count':dead,'error_log_count_24h':errors,'details_json':json.dumps(details,default=str)}).insert(ignore_permissions=True)
 if overall in ('Warning','Critical') and cint(settings.get('enable_health_alerts')):
  recipients=[x.strip() for x in (settings.get('health_alert_recipients') or '').splitlines() if x.strip()]
  if recipients: frappe.sendmail(recipients=recipients,subject=f'Hotel PMS health {overall}: {frappe.local.site}',message=f'Disk used: {used}%<br>Backup age: {age}<br>Failed sync: {failed_sync}<br>Dead webhooks: {dead}',reference_doctype=doc.doctype,reference_name=doc.name)
 return doc.name

@frappe.whitelist()
def verify_latest_backup():
 if not is_privileged() and 'Hotel Manager' not in frappe.get_roles(): frappe.throw(_('Not permitted'),frappe.PermissionError)
 files=_backup_files()
 if not files: frappe.throw(_('No backup file found in the site backup directory.'))
 path=files[0]; h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 key=f"BACKUP::{frappe.local.site}::{path.name}"
 existing=frappe.db.get_value('Hotel Backup Verification',{'idempotency_key':key},'name')
 if existing:return frappe.get_doc('Hotel Backup Verification',existing).as_dict()
 doc=frappe.get_doc({'doctype':'Hotel Backup Verification','site_name':frappe.local.site,'backup_path':str(path),'backup_created_at':get_datetime(path.stat().st_mtime),'file_size_mb':round(path.stat().st_size/1024/1024,2),'sha256':h.hexdigest(),'verification_status':'Verified','verified_at':now_datetime(),'idempotency_key':key,'notes':'Checksum and readable-file verification only. Complete a restore drill on an isolated site before production approval.'}).insert(ignore_permissions=True)
 return doc.as_dict()

def cleanup_platform_records():
 now=now_datetime()
 frappe.db.delete('Hotel API Idempotency',{'expires_at':('<',now)})
 retention=cint(frappe.db.get_single_value('Hotel PMS Settings','platform_log_retention_days') or 90)
 cutoff=add_to_date(now,days=-retention)
 frappe.db.delete('Hotel System Health Snapshot',{'captured_at':('<',cutoff)})


def worker_heartbeat():
    frappe.db.set_single_value('Hotel PMS Settings','last_worker_heartbeat',now_datetime(),update_modified=False)

def get_storage_report():
    site=Path(frappe.get_site_path()); rows=[];total=0
    for label,folder in [('public',site/'public'/'files'),('private',site/'private'/'files'),('backups',site/'private'/'backups')]:
        size=0;count=0
        if folder.exists():
            for path in folder.rglob('*'):
                if path.is_file():
                    count+=1
                    try:size+=path.stat().st_size
                    except OSError:pass
        total+=size;rows.append({'area':label,'files':count,'size_gb':round(size/1024**3,3)})
    return {'total_gb':round(total/1024**3,3),'areas':rows}

def get_access_review():
    hotel_roles=('Hotel Manager','Front Desk','Night Auditor','Housekeeping','Housekeeping Supervisor','Engineering','Engineering Supervisor','Hotel Sales','Banquet','Revenue Manager','Cashier','Credit Manager','Restaurant Cashier','Restaurant Captain','Kitchen','Laundry','Guest Services','Hotel API User')
    placeholders=', '.join(['%s']*len(hotel_roles))
    users=frappe.db.sql(f"""select distinct hr.parent from `tabHas Role` hr inner join `tabUser` u on u.name=hr.parent where hr.role in ({placeholders}) and u.enabled=1 and u.user_type='System User'""",hotel_roles,as_dict=True)
    missing=[r.parent for r in users if not frappe.db.exists('Hotel User Property Access',{'user':r.parent,'enabled':1}) and r.parent!='Administrator']
    stale=frappe.db.count('Hotel User Property Access',{'enabled':1,'reviewed_at':('is','not set')})
    return {'users_missing_property':len(missing),'missing_users':missing[:20],'assignments_not_reviewed':stale}

@frappe.whitelist()
def review_property_access(access_names):
    if not is_privileged():frappe.throw(_('Only System Manager may review property access.'),frappe.PermissionError)
    if isinstance(access_names,str):
        try:access_names=json.loads(access_names)
        except Exception:access_names=[access_names]
    for name in access_names or []:frappe.db.set_value('Hotel User Property Access',name,{'reviewed_by':frappe.session.user,'reviewed_at':now_datetime()},update_modified=False)
    return {'reviewed':len(access_names or [])}

def review_privacy_retention():
    today=now_datetime().date()
    rows=frappe.get_all('Hotel Guest Profile',filters={'retention_until':('<',today),'status':'Active','privacy_status':'Active'},fields=['name','customer'])
    flagged=0
    for row in rows:
        active=frappe.db.count('Hotel Reservation',{'guest':row.customer,'status':('in',['Tentative','Confirmed','Checked In'])})
        outstanding=frappe.db.sql("select coalesce(sum(outstanding_amount),0) from `tabSales Invoice` where customer=%s and docstatus=1",row.customer)[0][0]
        if not active and not outstanding:
            frappe.db.set_value('Hotel Guest Profile',row.name,'privacy_status','Pending Anonymization',update_modified=False);flagged+=1
    return {'flagged':flagged}
