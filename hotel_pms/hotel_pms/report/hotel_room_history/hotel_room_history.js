frappe.query_reports["Hotel Room History"]={filters:[
 {fieldname:"room",label:__("Room"),fieldtype:"Link",options:"Hotel Room",reqd:1},
 {fieldname:"from_date",label:__("From Date"),fieldtype:"Date",default:frappe.datetime.add_months(frappe.datetime.get_today(),-3)},
 {fieldname:"to_date",label:__("To Date"),fieldtype:"Date",default:frappe.datetime.get_today()}
]};
