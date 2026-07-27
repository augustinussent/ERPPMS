frappe.ui.form.on("Hotel City Ledger Folio", {
  refresh(frm) {
    if (!frm.is_new() && (frm.doc.charges || []).some(x => !x.is_void && !x.sales_invoice)) {
      frm.add_custom_button(__("Create Sales Invoice"), async () => {
        const r = await frappe.call({ method: "hotel_pms.billing.create_city_ledger_sales_invoice", args: { folio: frm.doc.name }, freeze: true });
        frappe.set_route("Form", "Sales Invoice", r.message.sales_invoice);
      }, __("ERPNext"));
    }
  },
});
