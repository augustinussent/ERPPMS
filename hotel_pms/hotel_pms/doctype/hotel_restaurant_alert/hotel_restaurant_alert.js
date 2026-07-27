frappe.ui.form.on("Hotel Restaurant Alert", {
  refresh(frm) {
    if (frm.is_new()) return;
    if (frm.doc.reference_doctype && frm.doc.reference_name) {
      frm.add_custom_button(__("Open Reference"), () => frappe.set_route("Form", frm.doc.reference_doctype, frm.doc.reference_name));
    }
    if (frm.doc.status === "Open") {
      frm.add_custom_button(__("Acknowledge"), () => frm.set_value("status", "Acknowledged").then(() => frm.save()));
    }
    if (["Open", "Acknowledged"].includes(frm.doc.status)) {
      frm.add_custom_button(__("Resolve"), () => frm.set_value("status", "Resolved").then(() => frm.save()));
    }
  },
});
