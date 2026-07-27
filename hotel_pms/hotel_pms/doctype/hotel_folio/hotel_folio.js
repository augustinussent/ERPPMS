frappe.ui.form.on("Hotel Folio", {
  refresh(frm) {
    if (!frm.doc.sales_invoice && frm.doc.charges && frm.doc.charges.length) {
      frm.add_custom_button(__("Create Sales Invoice"), () => {
        frappe.call({
          method: "hotel_pms.api.create_sales_invoice",
          args: { folio: frm.doc.name },
          freeze: true,
          callback(r) {
            if (r.message && r.message.sales_invoice) {
              frappe.set_route("Form", "Sales Invoice", r.message.sales_invoice);
            }
          },
        });
      }, __("ERPNext"));
    }
  },
});
