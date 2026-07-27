from __future__ import annotations
import json,time,urllib.request,urllib.error
import frappe
from frappe import _
from frappe.utils import add_to_date,now_datetime
from hotel_pms.platform_rules import canonical_json,event_matches,retry_delay_seconds,webhook_signature
from hotel_pms.sync import make_sync_key

def _property_from_doc(doc):
 if doc.meta.has_field('property'):return doc.get('property')
 for link,target in [('reservation','Hotel Reservation'),('group_booking','Hotel Group Booking'),('outlet','Hotel Outlet'),('restaurant_order','Hotel Restaurant Order'),('cashier_shift','Hotel Cashier Shift')]:
  if doc.meta.has_field(link) and doc.get(link):return frappe.db.get_value(target,doc.get(link),'property')
 return None

def _event_name(doc,method):
 prefix={'Hotel Reservation':'reservation','Hotel Housekeeping Task':'housekeeping','Hotel Maintenance Ticket':'maintenance','Hotel Restaurant Order':'restaurant_order','Hotel Laundry Order':'laundry','Hotel Experience Booking':'experience','Sales Invoice':'sales_invoice','POS Invoice':'pos_invoice','Payment Entry':'payment','Purchase Invoice':'purchase_invoice'}.get(doc.doctype,doc.doctype.lower().replace(' ','_'))
 suffix={'after_insert':'created','on_update':'updated','on_submit':'submitted','on_cancel':'cancelled','on_trash':'deleted'}.get(method,method)
 return f'{prefix}.{suffix}'

def emit_document_event(doc,method=None):
 if not frappe.db.get_single_value('Hotel PMS Settings','enable_outbound_webhooks'):return
 event=_event_name(doc,method or 'updated');prop=_property_from_doc(doc)
 subs=frappe.get_all('Hotel Webhook Subscription',filters={'enabled':1},fields=['name','property','event_patterns'])
 payload={'event':event,'occurred_at':str(now_datetime()),'property':prop,'document':{'doctype':doc.doctype,'name':doc.name,'docstatus':doc.docstatus,'modified':str(doc.modified or now_datetime())}}
 for sub in subs:
  if sub.property and sub.property!=prop:continue
  if not event_matches((sub.event_patterns or '').splitlines(),event):continue
  key=make_sync_key('WEBHOOK',sub.name,event,doc.doctype,doc.name,str(doc.modified or now_datetime()))
  if frappe.db.exists('Hotel Webhook Delivery',key):continue
  frappe.get_doc({'doctype':'Hotel Webhook Delivery','subscription':sub.name,'property':prop,'event_name':event,'source_doctype':doc.doctype,'source_name':doc.name,'payload_json':canonical_json(payload),'idempotency_key':key,'status':'Pending','next_attempt_at':now_datetime()}).insert(ignore_permissions=True)

def _send(delivery):
 sub=frappe.get_doc('Hotel Webhook Subscription',delivery.subscription);from hotel_pms.hotel_pms.doctype.hotel_webhook_subscription.hotel_webhook_subscription import validate_webhook_url;validate_webhook_url(sub.endpoint_url);body=delivery.payload_json;timestamp=str(int(time.time()));signature=webhook_signature(sub.get_password('secret'),timestamp,body)
 req=urllib.request.Request(sub.endpoint_url,data=body.encode(),method='POST',headers={'Content-Type':'application/json','User-Agent':'Hotel-PMS/0.9','X-Hotel-Event':delivery.event_name,'X-Hotel-Timestamp':timestamp,'X-Hotel-Signature':f'sha256={signature}','X-Idempotency-Key':delivery.idempotency_key})
 try:
  with urllib.request.urlopen(req,timeout=int(sub.timeout_seconds or 15)) as response:
   excerpt=response.read(1000).decode(errors='replace');code=response.status
  if not 200<=code<300:raise RuntimeError(f'HTTP {code}: {excerpt}')
  delivery.db_set({'status':'Sent','attempts':delivery.attempts+1,'last_attempt_at':now_datetime(),'sent_at':now_datetime(),'response_code':code,'response_excerpt':excerpt,'last_error':None,'signature':signature},update_modified=False);sub.db_set('last_success_at',now_datetime(),update_modified=False)
 except Exception as exc:
  attempts=(delivery.attempts or 0)+1;max_attempts=int(sub.max_attempts or frappe.db.get_single_value('Hotel PMS Settings','webhook_max_attempts') or 8);status='Dead Letter' if attempts>=max_attempts else 'Retry';next_at=add_to_date(now_datetime(),seconds=retry_delay_seconds(attempts,int(frappe.db.get_single_value('Hotel PMS Settings','webhook_initial_backoff_seconds') or 60)))
  delivery.db_set({'status':status,'attempts':attempts,'last_attempt_at':now_datetime(),'next_attempt_at':next_at,'last_error':str(exc)[:500],'signature':signature},update_modified=False);sub.db_set('last_failure_at',now_datetime(),update_modified=False)

@frappe.whitelist()
def process_webhook_queue(limit=50):
 rows=frappe.get_all('Hotel Webhook Delivery',filters={'status':('in',['Pending','Retry']),'next_attempt_at':('<=',now_datetime())},pluck='name',order_by='next_attempt_at asc',limit=min(int(limit),200))
 for name in rows:
  try:
   frappe.db.sql('select name from `tabHotel Webhook Delivery` where name=%s for update',name);doc=frappe.get_doc('Hotel Webhook Delivery',name)
   if doc.status not in ('Pending','Retry'):continue
   doc.db_set('status','Processing',update_modified=False);_send(doc)
  except Exception:frappe.log_error(frappe.get_traceback(),'Hotel webhook queue')
 return {'processed':len(rows)}

@frappe.whitelist()
def replay_delivery(delivery):
 if 'System Manager' not in frappe.get_roles() and 'Hotel Manager' not in frappe.get_roles():frappe.throw(_('Not permitted'),frappe.PermissionError)
 doc=frappe.get_doc('Hotel Webhook Delivery',delivery);doc.db_set({'status':'Retry','next_attempt_at':now_datetime(),'last_error':None},update_modified=True);return {'delivery':doc.name,'status':'Retry'}
