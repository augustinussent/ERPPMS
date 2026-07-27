from __future__ import annotations
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
ROLES=['Hotel API User','Hotel Cross Property Manager']
def setup_platform():
 for role in ROLES:
  if not frappe.db.exists('Role',role):frappe.get_doc({'doctype':'Role','role_name':role}).insert(ignore_permissions=True)
 create_custom_fields({'Hotel ERP Sync Log':[{'fieldname':'property','label':'Property','fieldtype':'Link','options':'Hotel Property','insert_after':'operation','read_only':1}]},update=True)
 for dt,fields in {'Hotel User Property Access':['user','property','enabled'],'Hotel Migration Row':['batch','row_number','status'],'Hotel Webhook Delivery':['status','next_attempt_at','property'],'Hotel API Idempotency':['expires_at','user','endpoint'],'Hotel System Health Snapshot':['captured_at','overall_status']}.items():
  try:frappe.db.add_index(dt,fields)
  except Exception:pass
