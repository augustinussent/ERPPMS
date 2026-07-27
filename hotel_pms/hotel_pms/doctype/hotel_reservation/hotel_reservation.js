frappe.ui.form.on("Hotel Reservation", {
  refresh(frm) {
    if (!frm.is_new() && ["Tentative", "Confirmed"].includes(frm.doc.status)) {
      frm.add_custom_button(__("Issue Pre-arrival Form"), async () => {
        const templates = await frappe.db.get_list("Hotel Prearrival Form Template", {filters:{property:frm.doc.property,enabled:1},fields:["name","title"]});
        if (!templates.length) return frappe.msgprint(__("Configure an enabled pre-arrival form template first."));
        const d = new frappe.ui.Dialog({title:__("Issue Pre-arrival Form"),fields:[{fieldname:"template",label:__("Template"),fieldtype:"Select",options:templates.map(x=>x.name).join("\n"),default:templates[0].name,reqd:1}],primary_action_label:__("Issue One-time Link"),primary_action:async values=>{
          const r=await frappe.call({method:"hotel_pms.prearrival.issue_prearrival_form",args:{reservation:frm.doc.name,template:values.template,request_key:`${frm.doc.name}:${Date.now()}`},freeze:true});d.hide();const x=r.message;if(x.url)frappe.msgprint({title:__("One-time Pre-arrival Link"),message:`<p>${__("Copy this link now. It is not stored in plaintext and can be submitted once.")}</p><textarea class="form-control" rows="4">${frappe.utils.escape_html(x.url)}</textarea>`,wide:true});else frappe.msgprint(__("A link was already issued. Revoke it before issuing a replacement."));frm.reload_doc();
        }});d.show();
      }, __("Guest"));
    }
    if (frm.doc.distribution_connection) {
      frm.add_custom_button(__("Open Distribution Event"), () => frappe.set_route("Form", "Hotel Distribution Event", frm.doc.external_event), __("Distribution"));
    }
  }
});
