frappe.ui.form.on("Hotel Rate Approval", {
  refresh(frm) {
    if (frm.doc.status === "Pending" && ["System Manager", "Hotel Manager", "Revenue Manager"].some(r => frappe.user_roles.includes(r))) {
      frm.add_custom_button(__("Approve"), async () => { await frm.set_value("status", "Approved"); await frm.save(); }, __("Decision"));
      frm.add_custom_button(__("Reject"), async () => { await frm.set_value("status", "Rejected"); await frm.save(); }, __("Decision"));
    }
  },
});
