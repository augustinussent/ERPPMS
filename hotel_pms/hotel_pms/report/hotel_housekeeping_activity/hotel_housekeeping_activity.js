frappe.query_reports["Hotel Housekeeping Activity"]={filters:[
 {fieldname:"property",label:__("Property"),fieldtype:"Link",options:"Hotel Property"},
 {fieldname:"from_date",label:__("From Date"),fieldtype:"Date",default:frappe.datetime.add_days(frappe.datetime.get_today(),-7)},
 {fieldname:"to_date",label:__("To Date"),fieldtype:"Date",default:frappe.datetime.get_today()},
 {fieldname:"assigned_to",label:__("Housekeeper"),fieldtype:"Link",options:"User"},
 {fieldname:"room",label:__("Room"),fieldtype:"Link",options:"Hotel Room"},
 {fieldname:"task_type",label:__("Task Type"),fieldtype:"Select",options:"\nStayover Clean\nCheckout Clean\nPost-Maintenance Cleaning\nReclean\nDeep Clean\nPickup\nInspection\nTurndown"},
 {fieldname:"status",label:__("Status"),fieldtype:"Select",options:"\nOpen\nAssigned\nIn Progress\nPaused\nWaiting Engineering\nReady for Inspection\nReclean Required\nCompleted\nCancelled"}
]};
