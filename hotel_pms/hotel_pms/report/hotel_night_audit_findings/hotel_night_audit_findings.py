import frappe

def execute(filters=None):
    filters=filters or {}
    columns=[
      {"fieldname":"business_date","label":"Business Date","fieldtype":"Date","width":110},
      {"fieldname":"property","label":"Property","fieldtype":"Link","options":"Hotel Property","width":160},
      {"fieldname":"severity","label":"Severity","fieldtype":"Data","width":90},
      {"fieldname":"finding_type","label":"Finding Type","fieldtype":"Data","width":180},
      {"fieldname":"status","label":"Status","fieldtype":"Data","width":110},
      {"fieldname":"reference_doctype","label":"Reference Type","fieldtype":"Data","width":150},
      {"fieldname":"reference_name","label":"Reference","fieldtype":"Dynamic Link","options":"reference_doctype","width":170},
      {"fieldname":"amount","label":"Amount / Variance","fieldtype":"Currency","width":130},
      {"fieldname":"description","label":"Description","fieldtype":"Data","width":320},
      {"fieldname":"recommended_action","label":"Recommended Action","fieldtype":"Data","width":260},
    ]
    db_filters={}
    for key in ("property","business_date","severity","status","finding_type"):
        if filters.get(key): db_filters[key]=filters[key]
    data=frappe.get_all("Hotel Night Audit Finding",filters=db_filters,fields=[c["fieldname"] for c in columns],order_by="business_date desc, severity asc, modified desc",limit_page_length=0)
    return columns,data
