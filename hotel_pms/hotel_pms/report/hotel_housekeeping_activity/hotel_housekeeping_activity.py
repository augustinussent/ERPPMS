from __future__ import annotations

import frappe
from frappe import _


def execute(filters=None):
    filters=frappe._dict(filters or {}); conditions=["1=1"]; values={}
    for field in ("property","assigned_to","status","task_type","room"):
        if filters.get(field): conditions.append(f"h.{field}=%({field})s"); values[field]=filters.get(field)
    if filters.from_date: conditions.append("h.task_date >= %(from_date)s"); values["from_date"]=filters.from_date
    if filters.to_date: conditions.append("h.task_date <= %(to_date)s"); values["to_date"]=filters.to_date
    rows=frappe.db.sql(f"""
      select h.name as task,h.task_date,h.property,h.room,r.room_number,h.task_type,h.status,h.priority,h.assigned_to,
             h.assigned_at,h.started_at,h.completed_at,h.inspected_at,h.cleaning_minutes,h.total_pause_minutes,h.turnaround_minutes,h.first_pass,h.inspection
      from `tabHotel Housekeeping Task` h left join `tabHotel Room` r on r.name=h.room
      where {' and '.join(conditions)} order by h.task_date desc,h.priority_score desc,h.creation desc
    """,values,as_dict=True)
    columns=[
      {"label":_("Task"),"fieldname":"task","fieldtype":"Link","options":"Hotel Housekeeping Task","width":145},
      {"label":_("Date"),"fieldname":"task_date","fieldtype":"Date","width":90},
      {"label":_("Room"),"fieldname":"room","fieldtype":"Link","options":"Hotel Room","width":110},
      {"label":_("Type"),"fieldname":"task_type","fieldtype":"Data","width":145},
      {"label":_("Status"),"fieldname":"status","fieldtype":"Data","width":120},
      {"label":_("Priority"),"fieldname":"priority","fieldtype":"Data","width":80},
      {"label":_("Housekeeper"),"fieldname":"assigned_to","fieldtype":"Link","options":"User","width":170},
      {"label":_("Assigned"),"fieldname":"assigned_at","fieldtype":"Datetime","width":145},
      {"label":_("Started"),"fieldname":"started_at","fieldtype":"Datetime","width":145},
      {"label":_("Completed"),"fieldname":"completed_at","fieldtype":"Datetime","width":145},
      {"label":_("Inspected"),"fieldname":"inspected_at","fieldtype":"Datetime","width":145},
      {"label":_("Cleaning Min"),"fieldname":"cleaning_minutes","fieldtype":"Float","width":100},
      {"label":_("Pause Min"),"fieldname":"total_pause_minutes","fieldtype":"Float","width":90},
      {"label":_("Turnaround Min"),"fieldname":"turnaround_minutes","fieldtype":"Float","width":110},
      {"label":_("First Pass"),"fieldname":"first_pass","fieldtype":"Check","width":80},
    ]; return columns,rows
