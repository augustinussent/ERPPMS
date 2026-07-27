frappe.ui.form.on("Hotel Maintenance Ticket", {
  refresh(frm) {
    if (frm.is_new()) return;
    const call = async (method,args={})=>{await frappe.call({method,args:{ticket:frm.doc.name,...args},freeze:true});await frm.reload_doc();};
    if (["Open","Assigned"].includes(frm.doc.status)) frm.add_custom_button(__("Acknowledge"),()=>call("hotel_pms.operations.acknowledge_maintenance"),__("Actions"));
    if (["Open","Acknowledged","Assigned","Paused","Waiting Vendor","Waiting Parts"].includes(frm.doc.status)) frm.add_custom_button(__("Start"),()=>call("hotel_pms.operations.start_maintenance"),__("Actions"));
    if (frm.doc.status==="In Progress") {
      frm.add_custom_button(__("Complete Repair"),()=>completeDialog(frm,call),__("Actions"));
      frm.add_custom_button(__("Pause / Wait"),()=>pauseDialog(frm,call),__("Actions"));
    }
    if (frm.doc.status==="Resolved" && (frappe.user_roles.includes("Engineering Supervisor")||frappe.user_roles.includes("Hotel Manager")||frappe.user_roles.includes("System Manager"))) frm.add_custom_button(__("Close"),()=>call("hotel_pms.operations.close_maintenance"),__("Actions"));
    if (["Repair Completed","Post-Maintenance Cleaning","Resolved","Closed"].includes(frm.doc.status)) frm.add_custom_button(__("Create SOP Candidate"),()=>call("hotel_pms.operations.create_sop_candidate"),__("Knowledge"));
    if (frm.doc.post_cleaning_task) frm.add_custom_button(__("Open Cleaning Task"),()=>frappe.set_route("Form","Hotel Housekeeping Task",frm.doc.post_cleaning_task),__("View"));
    if (frm.doc.room) frm.add_custom_button(__("Room History"),()=>frappe.set_route("query-report","Hotel Room History",{room:frm.doc.room}),__("View"));
    frm.add_custom_button(__("Operations Mobile"),()=>frappe.set_route("hotel-housekeeping-mobile"),__("View"));
  }
});
function pauseDialog(frm,call){const d=new frappe.ui.Dialog({title:__("Pause / Waiting"),fields:[{fieldname:"waiting_status",label:__("Status"),fieldtype:"Select",options:"Paused\nWaiting Vendor\nWaiting Parts",default:"Paused",reqd:1},{fieldname:"reason",label:__("Reason"),fieldtype:"Small Text",reqd:1}],primary_action_label:__("Save"),primary_action:async v=>{d.hide();await call("hotel_pms.operations.pause_maintenance",v);}});d.show();}
function completeDialog(frm,call){const d=new frappe.ui.Dialog({title:__("Complete Repair"),fields:[{fieldname:"root_cause",label:__("Root Cause"),fieldtype:"Small Text",reqd:1},{fieldname:"corrective_action",label:__("Corrective Action"),fieldtype:"Text",reqd:1},{fieldname:"materials_used",label:__("Materials / Parts"),fieldtype:"Text"},{fieldname:"prevention_notes",label:__("Prevention / HIKMAH"),fieldtype:"Text"},{fieldname:"post_maintenance_cleaning_required",label:__("Post-maintenance Cleaning Required"),fieldtype:"Check"},{fieldname:"cleaning_instructions",label:__("Practical Cleaning Instructions"),fieldtype:"Text",depends_on:"post_maintenance_cleaning_required"}],primary_action_label:__("Complete Repair"),primary_action:async v=>{d.hide();await call("hotel_pms.operations.complete_maintenance",{data:v,idempotency_key:`FORM-${Date.now()}`});}});d.show();}
