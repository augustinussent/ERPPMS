frappe.query_reports["Hotel Housekeeping Performance"] = {
 filters:[
  {fieldname:"property",label:__("Property"),fieldtype:"Link",options:"Hotel Property"},
  {fieldname:"from_date",label:__("From Date"),fieldtype:"Date",default:frappe.datetime.add_days(frappe.datetime.get_today(),-30)},
  {fieldname:"to_date",label:__("To Date"),fieldtype:"Date",default:frappe.datetime.get_today()},
  {fieldname:"housekeeper",label:__("Housekeeper"),fieldtype:"Link",options:"User"}
 ]
};
