import frappe

def execute(filters=None):
 f=frappe._dict(filters or {});cond={}
 if f.property:cond["property"]=f.property
 if f.from_date and f.to_date:cond["requested_at"]=("between",[f.from_date,f.to_date+" 23:59:59"])
 rows=frappe.get_all("Hotel Laundry Order",filters=cond,fields=["name","reservation","room","status","requested_at","promised_ready_at","ready_at","returned_at","overdue","total_amount","source"],order_by="requested_at desc")
 cols=[{"label":"Order","fieldname":"name","fieldtype":"Link","options":"Hotel Laundry Order","width":145},{"label":"Room","fieldname":"room","fieldtype":"Link","options":"Hotel Room","width":100},{"label":"Status","fieldname":"status","width":100},{"label":"Requested","fieldname":"requested_at","fieldtype":"Datetime","width":145},{"label":"Promised","fieldname":"promised_ready_at","fieldtype":"Datetime","width":145},{"label":"Ready","fieldname":"ready_at","fieldtype":"Datetime","width":145},{"label":"Overdue","fieldname":"overdue","fieldtype":"Check","width":75},{"label":"Amount","fieldname":"total_amount","fieldtype":"Currency","width":120}]
 return cols,rows
