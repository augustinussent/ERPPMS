from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate


def execute(filters=None):
    filters=frappe._dict(filters or {})
    conditions=["k.kot_date between %(from_date)s and %(to_date)s"]
    values={"from_date":getdate(filters.get("from_date")),"to_date":getdate(filters.get("to_date"))}
    if filters.get("property"):
        conditions.append("k.property=%(property)s"); values["property"]=filters.property
    if filters.get("outlet"):
        conditions.append("k.outlet=%(outlet)s"); values["outlet"]=filters.outlet
    if filters.get("stock_status"):
        conditions.append("k.stock_posting_status=%(stock_status)s"); values["stock_status"]=filters.stock_status
    rows=frappe.db.sql(f"""select k.kot_date,k.property,k.outlet,k.name kitchen_ticket,k.restaurant_order,
        o.inventory_posting_policy,k.stock_posting_status,k.stock_entry,se.docstatus stock_entry_docstatus,
        k.stock_posted_at,k.stock_error
        from `tabHotel Kitchen Ticket` k
        inner join `tabHotel Outlet` o on o.name=k.outlet
        left join `tabStock Entry` se on se.name=k.stock_entry
        where {' and '.join(conditions)} order by k.kot_date desc,k.daily_kot_number desc""",values,as_dict=True)
    columns=[
        {"fieldname":"kot_date","label":_("Date"),"fieldtype":"Date","width":95},
        {"fieldname":"property","label":_("Property"),"fieldtype":"Link","options":"Hotel Property","width":150},
        {"fieldname":"outlet","label":_("Outlet"),"fieldtype":"Link","options":"Hotel Outlet","width":140},
        {"fieldname":"kitchen_ticket","label":_("KOT"),"fieldtype":"Link","options":"Hotel Kitchen Ticket","width":150},
        {"fieldname":"restaurant_order","label":_("Order"),"fieldtype":"Link","options":"Hotel Restaurant Order","width":150},
        {"fieldname":"inventory_posting_policy","label":_("Inventory Policy"),"fieldtype":"Data","width":180},
        {"fieldname":"stock_posting_status","label":_("Stock Status"),"fieldtype":"Data","width":125},
        {"fieldname":"stock_entry","label":_("Stock Entry"),"fieldtype":"Link","options":"Stock Entry","width":150},
        {"fieldname":"stock_entry_docstatus","label":_("SE Docstatus"),"fieldtype":"Int","width":90},
        {"fieldname":"stock_error","label":_("Error"),"fieldtype":"Small Text","width":260},
    ]
    return columns,rows
