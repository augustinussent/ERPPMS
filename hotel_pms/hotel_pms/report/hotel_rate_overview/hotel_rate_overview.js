frappe.query_reports["Hotel Rate Overview"] = {filters:[
 {fieldname:"property",label:__("Property"),fieldtype:"Link",options:"Hotel Property",reqd:1},
 {fieldname:"start_date",label:__("Start Date"),fieldtype:"Date",default:frappe.datetime.get_today(),reqd:1},
 {fieldname:"days",label:__("Days"),fieldtype:"Int",default:14}
]};
