from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_datetime


def execute(filters=None):
    filters=frappe._dict(filters or {})
    if not filters.room: return get_columns(), []
    from_date=filters.from_date; to_date=filters.to_date
    rows=[]
    cond="room=%(room)s"; vals={"room":filters.room}
    if from_date: cond+=" and event_at >= %(from_date)s"; vals["from_date"]=from_date
    if to_date: cond+=" and event_at < date_add(%(to_date)s, interval 1 day)"; vals["to_date"]=to_date
    for r in frappe.db.sql(f"select event_at,event_type,notes,source_doctype,source_name,changed_by,new_operational_status,new_housekeeping_status from `tabHotel Room Status Log` where {cond}",vals,as_dict=True):
        rows.append({"timestamp":r.event_at,"category":"Room Status","event":r.event_type,"status":f"{r.new_operational_status or ''} / {r.new_housekeeping_status or ''}","user":r.changed_by,"details":r.notes,"reference_doctype":r.source_doctype,"reference_name":r.source_name})
    hfilters={"room":filters.room}; mfilters={"room":filters.room}; lfilters={"room":filters.room}
    if from_date:
        hfilters["creation"]=(">=",from_date);mfilters["reported_at"]=(">=",from_date);lfilters["found_at"]=(">=",from_date)
    if to_date:
        from frappe.utils import add_days
        upper=add_days(to_date,1)
        hfilters["creation"]=("<",upper) if not from_date else ("between",[from_date,upper])
        mfilters["reported_at"]=("<",upper) if not from_date else ("between",[from_date,upper])
        lfilters["found_at"]=("<",upper) if not from_date else ("between",[from_date,upper])
    for r in frappe.get_all("Hotel Housekeeping Task",filters=hfilters,fields=["name","creation","task_type","status","assigned_to","cleaning_minutes","notes"]): rows.append({"timestamp":r.creation,"category":"Housekeeping","event":r.task_type,"status":r.status,"user":r.assigned_to,"details":f"{r.cleaning_minutes or 0} min · {r.notes or ''}","reference_doctype":"Hotel Housekeeping Task","reference_name":r.name})
    for r in frappe.get_all("Hotel Maintenance Ticket",filters=mfilters,fields=["name","reported_at","subject","status","priority","reported_by","root_cause","prevention_notes"]): rows.append({"timestamp":r.reported_at,"category":"Maintenance","event":r.subject,"status":f"{r.status} · {r.priority}","user":r.reported_by,"details":f"Root cause: {r.root_cause or '-'}; Prevention: {r.prevention_notes or '-'}","reference_doctype":"Hotel Maintenance Ticket","reference_name":r.name})
    for r in frappe.get_all("Hotel Lost and Found",filters=lfilters,fields=["name","found_at","item_description","status","found_by","storage_location"]): rows.append({"timestamp":r.found_at,"category":"Lost & Found","event":r.item_description,"status":r.status,"user":r.found_by,"details":r.storage_location,"reference_doctype":"Hotel Lost and Found","reference_name":r.name})
    rows.sort(key=lambda r:get_datetime(r.timestamp) if r.timestamp else get_datetime("1900-01-01"),reverse=True)
    return get_columns(),rows

def get_columns():
    return [
      {"label":_("Time"),"fieldname":"timestamp","fieldtype":"Datetime","width":150},
      {"label":_("Category"),"fieldname":"category","fieldtype":"Data","width":115},
      {"label":_("Event"),"fieldname":"event","fieldtype":"Data","width":220},
      {"label":_("Status"),"fieldname":"status","fieldtype":"Data","width":160},
      {"label":_("User"),"fieldname":"user","fieldtype":"Link","options":"User","width":160},
      {"label":_("Details"),"fieldname":"details","fieldtype":"Data","width":350},
      {"label":_("Reference Type"),"fieldname":"reference_doctype","fieldtype":"Data","width":150},
      {"label":_("Reference"),"fieldname":"reference_name","fieldtype":"Dynamic Link","options":"reference_doctype","width":160},
    ]
