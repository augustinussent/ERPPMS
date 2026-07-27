frappe.ui.form.on("Hotel Payment Correction", {
  refresh(frm) {
    if (frm.doc.status === "Pending Approval" && frappe.user.has_role(["Hotel Manager", "Accounts Manager", "System Manager"])) {
      frm.add_custom_button(__("Approve"), async () => {
        await frappe.call({method:"hotel_pms.intelligence.approve_payment_correction", args:{correction:frm.doc.name}, freeze:true});
        frm.reload_doc();
      });
    }
    if (frm.doc.status === "Approved" && frappe.user.has_role(["Hotel Manager", "Accounts Manager", "System Manager"])) {
      frm.add_custom_button(__("Execute Governed Correction"), async () => {
        await frappe.call({method:"hotel_pms.intelligence.execute_payment_correction", args:{correction:frm.doc.name}, freeze:true});
        frm.reload_doc();
      });
    }
  },
  payment_entry: async function(frm) {
    if (!frm.doc.payment_entry) return;
    const r=await frappe.call({method:"hotel_pms.intelligence.preview_payment_correction",args:{payment_entry:frm.doc.payment_entry}});
    const p=r.message||{};
    frm.set_value("property",p.property);
    frm.set_value("reservation",p.reservation);
    frm.set_value("mode_of_payment",p.mode_of_payment);
    frm.set_value("requested_action",(p.allowed_actions||[])[0]);
    frm.set_value("amount",p.maximum_refundable||0);
    frappe.msgprint({title:__("Correction Matrix"),indicator:"blue",message:`${frappe.utils.escape_html(p.reason||"")}<br>${__("Allowed")}: ${(p.allowed_actions||[]).map(frappe.utils.escape_html).join(", ")}`});
  }
});
