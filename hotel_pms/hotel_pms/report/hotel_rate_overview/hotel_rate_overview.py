
import frappe
from frappe.utils import add_days, cint, getdate
from hotel_pms.revenue import quote_stay


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = [
        {"fieldname":"rate_date","label":"Date","fieldtype":"Date","width":100},
        {"fieldname":"room_type","label":"Room Type","fieldtype":"Link","options":"Hotel Room Type","width":170},
        {"fieldname":"rate_plan","label":"Rate Plan","fieldtype":"Link","options":"Hotel Rate Plan","width":200},
        {"fieldname":"effective_rate","label":"Effective Rate","fieldtype":"Currency","width":130},
        {"fieldname":"floor_rate","label":"Floor Rate","fieldtype":"Currency","width":120},
        {"fieldname":"restriction","label":"Restriction / Error","fieldtype":"Data","width":300},
    ]
    start = getdate(filters.start_date)
    days = max(1, min(cint(filters.days or 14), 62))
    plans = frappe.get_all("Hotel Rate Plan", filters={"property":filters.property,"enabled":1}, fields=["name","room_type"])
    data=[]
    for idx in range(days):
        day=add_days(start,idx)
        for plan in plans:
            try:
                q=quote_stay(filters.property,plan.room_type,plan.name,str(day),str(add_days(day,1)))
                row=q["daily_rates"][0]
                data.append({"rate_date":day,"room_type":plan.room_type,"rate_plan":plan.name,"effective_rate":row["rate"],"floor_rate":row["floor_rate"],"restriction":""})
            except Exception as exc:
                data.append({"rate_date":day,"room_type":plan.room_type,"rate_plan":plan.name,"restriction":str(exc)})
    return columns,data
