frappe.ui.form.on("Hotel Integration Connection", {
  refresh(frm) {
    if (!frm.is_new()) {
      frm.add_custom_button(__("Test Connection"), async()=>{const r=await frappe.call({method:"hotel_pms.intelligence.test_integration_connection",args:{connection:frm.doc.name},freeze:true});frappe.msgprint({title:__("Connection Test"),indicator:r.message.passed?"green":"red",message:`<pre>${frappe.utils.escape_html(JSON.stringify(r.message,null,2))}</pre>`});frm.reload_doc();});
    }
  },
  integration(frm) {
    if (frm.doc.integration && !(frm.doc.go_live_checks||[]).length) {
      frappe.db.get_doc("Hotel Integration Definition",frm.doc.integration).then(def=>{
        (def.go_live_checks||[]).forEach(row=>{const child=frm.add_child("go_live_checks");child.check_code=row.check_code;child.title=row.title;child.mandatory=row.mandatory;child.status="Pending";});
        frm.refresh_field("go_live_checks");
      });
    }
  }
});
