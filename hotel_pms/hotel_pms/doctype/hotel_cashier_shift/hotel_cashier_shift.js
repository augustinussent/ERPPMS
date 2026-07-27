frappe.ui.form.on("Hotel Cashier Shift", {
  refresh(frm) {
    if (frm.is_new()) return;
    frm.add_custom_button(__("Open Cashier Console"), () => {
      frappe.route_options = { cashier_shift: frm.doc.name };
      frappe.set_route("hotel-cashier");
    });
    frm.add_custom_button(__("Restaurant Control"), () => frappe.set_route("hotel-restaurant-control"));
    if (frm.doc.pos_opening_entry) {
      frm.add_custom_button(__("Open POS Opening Entry"), () => frappe.set_route("Form", "POS Opening Entry", frm.doc.pos_opening_entry), __("ERPNext POS"));
    } else if (frm.doc.outlet && frm.doc.status === "Open") {
      frm.add_custom_button(__("Link POS Opening Entry"), () => {
        frappe.prompt({ fieldname: "entry", label: __("POS Opening Entry"), fieldtype: "Link", options: "POS Opening Entry", reqd: 1 },
          values => frappe.call({ method: "hotel_pms.restaurant_controls.link_pos_opening_entry", args: { shift: frm.doc.name, pos_opening_entry: values.entry }, freeze: true }).then(() => frm.reload_doc()));
      }, __("ERPNext POS"));
    }
    if (frm.doc.pos_closing_entry) {
      frm.add_custom_button(__("Open POS Closing Entry"), () => frappe.set_route("Form", "POS Closing Entry", frm.doc.pos_closing_entry), __("ERPNext POS"));
    } else if (frm.doc.outlet && ["Open", "Closing Review"].includes(frm.doc.status)) {
      frm.add_custom_button(__("Link POS Closing Entry"), () => {
        frappe.prompt({ fieldname: "entry", label: __("POS Closing Entry"), fieldtype: "Link", options: "POS Closing Entry", reqd: 1 },
          values => frappe.call({ method: "hotel_pms.restaurant_controls.link_pos_closing_entry", args: { shift: frm.doc.name, pos_closing_entry: values.entry }, freeze: true }).then(() => frm.reload_doc()));
      }, __("ERPNext POS"));
    }
  },
});
