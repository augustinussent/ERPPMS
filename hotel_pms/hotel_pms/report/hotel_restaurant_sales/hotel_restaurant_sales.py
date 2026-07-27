import frappe

def execute(filters=None):
 f=frappe._dict(filters or {}); cond={"status":"Billed"};
 if f.property:cond["property"]=f.property
 if f.outlet:cond["outlet"]=f.outlet
 if f.from_date and f.to_date:cond["ordered_at"]=("between",[f.from_date,f.to_date+" 23:59:59"])
 rows=frappe.get_all("Hotel Restaurant Order",filters=cond,fields=["name","ordered_at","property","outlet","service_type","table","room","grand_total","status"],order_by="ordered_at desc")
 cols=[{"label":"Order","fieldname":"name","fieldtype":"Link","options":"Hotel Restaurant Order","width":150},{"label":"Ordered","fieldname":"ordered_at","fieldtype":"Datetime","width":145},{"label":"Outlet","fieldname":"outlet","fieldtype":"Link","options":"Hotel Outlet","width":160},{"label":"Service","fieldname":"service_type","width":100},{"label":"Table","fieldname":"table","width":110},{"label":"Room","fieldname":"room","width":100},{"label":"Total","fieldname":"grand_total","fieldtype":"Currency","width":120}]
 return cols,rows
