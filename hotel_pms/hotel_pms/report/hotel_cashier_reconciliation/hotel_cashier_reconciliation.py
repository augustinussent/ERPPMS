
import frappe


def execute(filters=None):
    filters=frappe._dict(filters or {})
    columns=[
      {"fieldname":"name","label":"Shift","fieldtype":"Link","options":"Hotel Cashier Shift","width":150},
      {"fieldname":"property","label":"Property","fieldtype":"Link","options":"Hotel Property","width":160},
      {"fieldname":"cashier","label":"Cashier","fieldtype":"Link","options":"User","width":180},
      {"fieldname":"opened_at","label":"Opened","fieldtype":"Datetime","width":150},
      {"fieldname":"closed_at","label":"Closed","fieldtype":"Datetime","width":150},
      {"fieldname":"opening_float","label":"Opening","fieldtype":"Currency","width":110},
      {"fieldname":"cash_receipts","label":"Receipts","fieldtype":"Currency","width":110},
      {"fieldname":"cash_refunds","label":"Refunds","fieldtype":"Currency","width":110},
      {"fieldname":"expected_cash","label":"Expected","fieldtype":"Currency","width":110},
      {"fieldname":"counted_cash","label":"Counted","fieldtype":"Currency","width":110},
      {"fieldname":"variance","label":"Variance","fieldtype":"Currency","width":110},
      {"fieldname":"status","label":"Status","fieldtype":"Data","width":100},
    ]
    cond={}
    if filters.property: cond["property"]=filters.property
    if filters.from_date and filters.to_date: cond["opened_at"]=("between",[filters.from_date,filters.to_date+" 23:59:59"])
    return columns,frappe.get_all("Hotel Cashier Shift",filters=cond,fields=[c["fieldname"] for c in columns],order_by="opened_at desc")
