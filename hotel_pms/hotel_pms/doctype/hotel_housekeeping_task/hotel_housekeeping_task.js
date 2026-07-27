frappe.ui.form.on("Hotel Housekeeping Task", {
  refresh(frm) {
    if (frm.is_new()) return;
    const call = async (method, args={}) => { await frappe.call({method, args:{task:frm.doc.name,...args}, freeze:true}); await frm.reload_doc(); };
    if (["Open","Assigned","Reclean Required"].includes(frm.doc.status)) frm.add_custom_button(__("Start"),()=>call("hotel_pms.operations.start_housekeeping_task"),__("Actions"));
    if (frm.doc.status==="In Progress") {
      frm.add_custom_button(__("Complete Cleaning"),()=>call("hotel_pms.operations.complete_housekeeping_task"),__("Actions"));
      frm.add_custom_button(__("Pause"),()=>pauseDialog(frm,call),__("Actions"));
      frm.add_custom_button(__("Report Lost & Found"),()=>lostDialog(frm,call),__("Report"));
      frm.add_custom_button(__("Report Damage"),()=>maintenanceDialog(frm),__("Report"));
    }
    if (["Paused","Waiting Engineering"].includes(frm.doc.status)) frm.add_custom_button(__("Resume"),()=>call("hotel_pms.operations.resume_housekeeping_task"),__("Actions"));
    if (frm.doc.status==="Ready for Inspection" && (frappe.user_roles.includes("Housekeeping Supervisor")||frappe.user_roles.includes("Hotel Manager")||frappe.user_roles.includes("System Manager"))) {
      frm.add_custom_button(__("Inspect"),()=>inspectionDialog(frm,call),__("Actions"));
    }
    frm.add_custom_button(__("Mobile Queue"),()=>frappe.set_route("hotel-housekeeping-mobile"),__("View"));
    frm.add_custom_button(__("Room History"),()=>frappe.set_route("query-report","Hotel Room History",{room:frm.doc.room}),__("View"));
  }
});

function pauseDialog(frm,call){const d=new frappe.ui.Dialog({title:__("Pause Cleaning"),fields:[{fieldname:"reason",label:__("Reason"),fieldtype:"Small Text",reqd:1},{fieldname:"waiting_engineering",label:__("Waiting Engineering"),fieldtype:"Check"}],primary_action_label:__("Pause"),primary_action:async v=>{d.hide();await call("hotel_pms.operations.pause_housekeeping_task",v);}});d.show();}
function inspectionDialog(frm,call){const d=new frappe.ui.Dialog({title:__("Supervisor Inspection"),fields:[{fieldname:"decision",label:__("Decision"),fieldtype:"Select",options:"Pass\nReclean Required",default:"Pass",reqd:1},{fieldname:"notes",label:__("Notes"),fieldtype:"Small Text"}],primary_action_label:__("Save"),primary_action:async v=>{d.hide();await call("hotel_pms.operations.inspect_housekeeping_task",{...v,idempotency_key:`FORM-${Date.now()}`});}});d.show();}
function lostDialog(frm,call){const d=new frappe.ui.Dialog({title:__("Lost & Found"),fields:[{fieldname:"item_category",label:__("Category"),fieldtype:"Select",options:"Cash\nDocument / ID\nJewelry\nElectronics\nClothing\nMedicine\nBag / Luggage\nKey / Card\nOther",default:"Other",reqd:1},{fieldname:"item_description",label:__("Description"),fieldtype:"Small Text",reqd:1},{fieldname:"found_location",label:__("Exact Location"),fieldtype:"Data"},{fieldname:"sensitive_item",label:__("Sensitive / High Value"),fieldtype:"Check"},{fieldname:"storage_location",label:__("Temporary Storage"),fieldtype:"Data"}],primary_action_label:__("Report"),primary_action:async v=>{d.hide();await call("hotel_pms.operations.report_lost_and_found",{data:v,idempotency_key:`FORM-${Date.now()}`});}});d.show();}
function maintenanceDialog(frm){const d=new frappe.ui.Dialog({title:__("Report Engineering Issue"),fields:[{fieldname:"subject",label:__("Subject"),fieldtype:"Data",reqd:1},{fieldname:"problem_category",label:__("Category"),fieldtype:"Select",options:"Electrical\nPlumbing\nHVAC / AC\nWater Heater\nFurniture / Fixture\nBuilding / Leakage\nNetwork / Wi-Fi\nAppliance\nLift\nSafety\nOther",default:"Other"},{fieldname:"description",label:__("Description"),fieldtype:"Text",reqd:1},{fieldname:"priority",label:__("Priority"),fieldtype:"Select",options:"Critical - Guest Complaint\nCritical - Safety / Spreading Damage\nHigh - Guest Visible\nMedium\nLow",default:"Medium"},{fieldname:"guest_impact",label:__("Guest Impact"),fieldtype:"Select",options:"None\nMinor Inconvenience\nMajor Inconvenience\nGuest Cannot Use Facility\nRoom Move Required",default:"None"},{fieldname:"affects_room_sale",label:__("Block Room From Sale"),fieldtype:"Check"}],primary_action_label:__("Create Ticket"),primary_action:async v=>{v.property=frm.doc.property;v.room=frm.doc.room;v.reservation=frm.doc.reservation;v.housekeeping_task=frm.doc.name;v.source="Housekeeping";d.hide();const r=await frappe.call({method:"hotel_pms.operations.report_maintenance_issue",args:{data:v,idempotency_key:`FORM-${Date.now()}`},freeze:true});frappe.set_route("Form","Hotel Maintenance Ticket",r.message.ticket);}});d.show();}
