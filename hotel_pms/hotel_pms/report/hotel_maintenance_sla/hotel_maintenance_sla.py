from __future__ import annotations
import frappe
from frappe import _

def execute(filters=None):
 filters=frappe._dict(filters or {});conds=["1=1"];vals={}
 for f in ("property","status","priority","sla_status","assigned_to","room"):
  if filters.get(f): conds.append(f"m.{f}=%({f})s");vals[f]=filters.get(f)
 if filters.from_date: conds.append("m.reported_at >= %(from_date)s");vals["from_date"]=filters.from_date
 if filters.to_date: conds.append("m.reported_at < date_add(%(to_date)s,interval 1 day)");vals["to_date"]=filters.to_date
 rows=frappe.db.sql(f"""select m.name as ticket,m.reported_at,m.property,m.room,m.subject,m.status,m.priority,m.source,m.assigned_to,m.sla_status,m.response_due_at,m.resolution_due_at,m.acknowledged_at,m.resolved_at,m.response_minutes,m.resolution_minutes,m.affects_room_sale from `tabHotel Maintenance Ticket` m where {' and '.join(conds)} order by case when m.sla_status like '%Breached%' then 1 else 2 end,m.reported_at desc""",vals,as_dict=True)
 columns=[
  {"label":_("Ticket"),"fieldname":"ticket","fieldtype":"Link","options":"Hotel Maintenance Ticket","width":145},{"label":_("Reported"),"fieldname":"reported_at","fieldtype":"Datetime","width":145},{"label":_("Room"),"fieldname":"room","fieldtype":"Link","options":"Hotel Room","width":100},{"label":_("Subject"),"fieldname":"subject","fieldtype":"Data","width":230},{"label":_("Status"),"fieldname":"status","fieldtype":"Data","width":125},{"label":_("Priority"),"fieldname":"priority","fieldtype":"Data","width":170},{"label":_("SLA"),"fieldname":"sla_status","fieldtype":"Data","width":120},{"label":_("Assigned"),"fieldname":"assigned_to","fieldtype":"Link","options":"User","width":160},{"label":_("Response Min"),"fieldname":"response_minutes","fieldtype":"Float","width":105},{"label":_("Resolution Min"),"fieldname":"resolution_minutes","fieldtype":"Float","width":115},{"label":_("Room Blocked"),"fieldname":"affects_room_sale","fieldtype":"Check","width":95}
 ];return columns,rows
