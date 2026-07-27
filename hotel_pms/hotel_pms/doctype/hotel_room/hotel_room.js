frappe.ui.form.on("Hotel Room", {
  refresh(frm) {
    if (!frm.is_new()) {
      frm.add_custom_button(__("Room History"),()=>frappe.set_route("query-report","Hotel Room History",{room:frm.doc.name}),__("View"));
      frm.add_custom_button(__("Operations Mobile"),()=>frappe.set_route("hotel-housekeeping-mobile"),__("View"));
    }
  }
});
