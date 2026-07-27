frappe.ui.form.on("Hotel Lost and Found", {
  refresh(frm) {
    if (frm.is_new()) return;
    if (frappe.user_roles.some(r=>["Housekeeping Supervisor","Front Desk","Hotel Manager","System Manager"].includes(r))) {
      frm.add_custom_button(__("Add Custody Event"),()=>custodyDialog(frm),__("Actions"));
    }
  }
});
function custodyDialog(frm){const d=new frappe.ui.Dialog({title:__("Chain of Custody"),fields:[{fieldname:"action",label:__("Action"),fieldtype:"Select",options:"Received by Supervisor\nStored\nGuest Contacted\nTransferred\nClaimed\nShipped\nReturned\nDisposed\nNote",reqd:1},{fieldname:"location",label:__("Location"),fieldtype:"Data"},{fieldname:"to_user",label:__("Handed To"),fieldtype:"Link",options:"User"},{fieldname:"notes",label:__("Notes"),fieldtype:"Small Text"}],primary_action_label:__("Save"),primary_action:async v=>{d.hide();await frappe.call({method:"hotel_pms.operations.add_lost_found_custody",args:{record:frm.doc.name,idempotency_key:`WEB-${Date.now()}`,...v},freeze:true});await frm.reload_doc();}});d.show();}
