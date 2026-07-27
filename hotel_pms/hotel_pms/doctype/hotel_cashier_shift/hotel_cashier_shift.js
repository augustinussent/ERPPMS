frappe.ui.form.on("Hotel Cashier Shift", {
  refresh(frm) {
    if (!frm.is_new()) frm.add_custom_button(__("Open Cashier Console"), () => { frappe.route_options = { cashier_shift: frm.doc.name }; frappe.set_route("hotel-cashier"); });
  },
});
