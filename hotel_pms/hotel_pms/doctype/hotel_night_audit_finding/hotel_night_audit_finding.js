frappe.ui.form.on("Hotel Night Audit Finding", {
  refresh(frm) {
    if (["Open"].includes(frm.doc.status)) {
      frm.add_custom_button(__("Acknowledge"), async()=>{await frappe.call({method:"hotel_pms.intelligence.acknowledge_finding",args:{finding:frm.doc.name},freeze:true});frm.reload_doc();});
    }
    if (["Open","Acknowledged"].includes(frm.doc.status)) {
      frm.add_custom_button(__("Resolve"), ()=>frappe.prompt([{fieldname:"resolution_notes",label:__("Resolution Notes"),fieldtype:"Small Text",reqd:1},{fieldname:"false_positive",label:__("False Positive"),fieldtype:"Check"}],async v=>{await frappe.call({method:"hotel_pms.intelligence.resolve_finding",args:{finding:frm.doc.name,resolution_notes:v.resolution_notes,false_positive:v.false_positive},freeze:true});frm.reload_doc();}));
    }
  }
});
