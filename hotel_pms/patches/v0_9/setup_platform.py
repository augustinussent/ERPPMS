import frappe
from hotel_pms.setup_platform import setup_platform

def execute():
    setup_platform()
    mappings={
      "Hotel Guest Access Token":"reservation", "Hotel Guest Action Log":"reservation", "Hotel Guest Consent":"reservation", "Hotel Voucher Redemption":"reservation"
    }
    for doctype,field in mappings.items():
        if frappe.db.has_column(doctype,"property"):
            frappe.db.sql(f"""update `tab{doctype}` x inner join `tabHotel Reservation` r on r.name=x.`{field}` set x.property=r.property where coalesce(x.property,'')=''""")
    if frappe.db.has_column("Hotel Guest Privacy Request","property"):
        frappe.db.sql("""update `tabHotel Guest Privacy Request` p inner join `tabHotel Guest Access Token` t on t.name=p.portal_token set p.property=t.property where coalesce(p.property,'')=''""")
