frappe.ui.form.on("Hotel Restaurant Print Job", {
  refresh(frm) {
    if (!frm.is_new() && ["Failed", "Queued"].includes(frm.doc.status)) {
      frm.add_custom_button(__("Retry Print"), () => frappe.call({
        method: "hotel_pms.restaurant_printing.process_restaurant_print_job",
        args: { job: frm.doc.name }, freeze: true,
      }).then(() => frm.reload_doc()));
    }
    if (!frm.is_new() && frm.doc.reference_doctype && frm.doc.reference_name) {
      frm.add_custom_button(__("Open Reference"), () => frappe.set_route("Form", frm.doc.reference_doctype, frm.doc.reference_name));
    }
  },
});
