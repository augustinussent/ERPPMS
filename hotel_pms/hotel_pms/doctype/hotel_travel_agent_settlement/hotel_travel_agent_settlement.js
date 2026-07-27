frappe.ui.form.on("Hotel Travel Agent Settlement", {
  refresh(frm) {
    if (!frm.is_new() && !frm.doc.purchase_invoice && frm.doc.total_commission > 0) {
      frm.add_custom_button(__("Create Purchase Invoice"), async () => {
        const r = await frappe.call({ method: "hotel_pms.revenue.create_travel_agent_purchase_invoice", args: { settlement: frm.doc.name }, freeze: true });
        frappe.set_route("Form", "Purchase Invoice", r.message.purchase_invoice);
      }, __("ERPNext"));
    }
  },
});
