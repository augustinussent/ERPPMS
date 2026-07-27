from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    conditions = ["h.status='Completed'", "h.assigned_to is not null"]
    values = {}
    if filters.property:
        conditions.append("h.property=%(property)s"); values["property"] = filters.property
    if filters.from_date:
        conditions.append("h.task_date >= %(from_date)s"); values["from_date"] = filters.from_date
    if filters.to_date:
        conditions.append("h.task_date <= %(to_date)s"); values["to_date"] = filters.to_date
    if filters.housekeeper:
        conditions.append("h.assigned_to=%(housekeeper)s"); values["housekeeper"] = filters.housekeeper
    rows = frappe.db.sql(f"""
        select h.assigned_to as housekeeper,
               count(*) as completed_tasks,
               sum(case when h.task_type='Checkout Clean' then 1 else 0 end) as checkout_rooms,
               sum(case when h.task_type='Stayover Clean' then 1 else 0 end) as stayover_rooms,
               sum(case when h.task_type='Post-Maintenance Cleaning' then 1 else 0 end) as post_maintenance_rooms,
               avg(nullif(h.cleaning_minutes,0)) as average_cleaning_minutes,
               avg(nullif(h.turnaround_minutes,0)) as average_turnaround_minutes,
               sum(case when h.first_pass=1 then 1 else 0 end) as first_pass_count,
               sum(case when h.inspection is not null and h.first_pass=0 then 1 else 0 end) as reclean_count,
               sum(case when h.target_ready_at is null or h.inspected_at <= h.target_ready_at then 1 else 0 end) as on_time_count
        from `tabHotel Housekeeping Task` h
        where {' and '.join(conditions)}
        group by h.assigned_to
        order by completed_tasks desc, h.assigned_to
    """, values, as_dict=True)
    for row in rows:
        row.first_pass_percent = flt(row.first_pass_count) / flt(row.completed_tasks) * 100 if row.completed_tasks else 0
        row.reclean_percent = flt(row.reclean_count) / flt(row.completed_tasks) * 100 if row.completed_tasks else 0
        row.on_time_percent = flt(row.on_time_count) / flt(row.completed_tasks) * 100 if row.completed_tasks else 0
    columns = [
        {"label":_("Housekeeper"),"fieldname":"housekeeper","fieldtype":"Link","options":"User","width":180},
        {"label":_("Completed"),"fieldname":"completed_tasks","fieldtype":"Int","width":90},
        {"label":_("Checkout"),"fieldname":"checkout_rooms","fieldtype":"Int","width":90},
        {"label":_("Stayover"),"fieldname":"stayover_rooms","fieldtype":"Int","width":90},
        {"label":_("Post-maint."),"fieldname":"post_maintenance_rooms","fieldtype":"Int","width":100},
        {"label":_("Avg Cleaning Min"),"fieldname":"average_cleaning_minutes","fieldtype":"Float","precision":1,"width":120},
        {"label":_("Avg Turnaround Min"),"fieldname":"average_turnaround_minutes","fieldtype":"Float","precision":1,"width":135},
        {"label":_("First-pass %"),"fieldname":"first_pass_percent","fieldtype":"Percent","width":100},
        {"label":_("Reclean %"),"fieldname":"reclean_percent","fieldtype":"Percent","width":90},
        {"label":_("On-time %"),"fieldname":"on_time_percent","fieldtype":"Percent","width":90},
    ]
    chart = {"data":{"labels":[r.housekeeper for r in rows],"datasets":[{"name":_("Completed Rooms"),"values":[r.completed_tasks for r in rows]}]},"type":"bar"}
    return columns, rows, None, chart
