frappe.ui.form.on("Hotel Intelligence Decision", {
  refresh(frm) {
    if (frm.doc.status === "Pending") {
      frm.add_custom_button(__("Approve Advisory Decision"), async()=>{await frappe.call({method:"hotel_pms.intelligence.approve_intelligence_decision",args:{decision:frm.doc.name},freeze:true});frm.reload_doc();});
      frm.add_custom_button(__("Reject"), ()=>frappe.prompt([{fieldname:"reason",label:__("Reason"),fieldtype:"Small Text",reqd:1}],async v=>{await frappe.call({method:"hotel_pms.intelligence.reject_intelligence_decision",args:{decision:frm.doc.name,reason:v.reason},freeze:true});frm.reload_doc();}));
    }
  }
});
