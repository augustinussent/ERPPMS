frappe.ui.form.on("Hotel Direct Bill Approval", {
  refresh(frm) {
    if (frm.doc.status === "Pending" && ["System Manager", "Hotel Manager", "Credit Manager", "Accounts Manager"].some(r => frappe.user_roles.includes(r))) {
      frm.add_custom_button(__("Approve"), async () => {
        const r = await frappe.call({ method: "hotel_pms.billing.approve_direct_bill", args: { approval: frm.doc.name, approved_amount: frm.doc.approved_amount || frm.doc.requested_amount }, freeze: true });
        frm.reload_doc();
      }, __("Decision"));
      frm.add_custom_button(__("Reject"), async () => { await frm.set_value("status", "Rejected"); await frm.save(); }, __("Decision"));
    }
  },
});
