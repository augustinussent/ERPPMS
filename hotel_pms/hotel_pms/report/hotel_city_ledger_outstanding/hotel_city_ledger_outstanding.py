
import frappe


def execute(filters=None):
    filters=frappe._dict(filters or {})
    columns=[
      {"fieldname":"account_name","label":"City Ledger Account","fieldtype":"Link","options":"Hotel City Ledger Account","width":200},
      {"fieldname":"customer","label":"Customer","fieldtype":"Link","options":"Customer","width":200},
      {"fieldname":"credit_limit","label":"Hotel Credit Limit","fieldtype":"Currency","width":130},
      {"fieldname":"outstanding","label":"ERPNext Outstanding","fieldtype":"Currency","width":150},
      {"fieldname":"available_credit","label":"Available Credit","fieldtype":"Currency","width":140},
      {"fieldname":"oldest_due_date","label":"Oldest Due","fieldtype":"Date","width":110},
    ]
    accounts=frappe.get_all("Hotel City Ledger Account",filters={"property":filters.property,"status":"Active", **({"customer":filters.customer} if filters.customer else {})},fields=["name as account_name","customer","credit_limit"])
    for row in accounts:
        inv=frappe.db.sql("""select coalesce(sum(outstanding_amount),0) outstanding,min(due_date) oldest_due_date from `tabSales Invoice` where customer=%s and docstatus=1 and outstanding_amount>0""",row.customer,as_dict=True)[0]
        row.update(inv); row["available_credit"]=max((row.credit_limit or 0)-(row.outstanding or 0),0) if row.credit_limit else None
    return columns,accounts
