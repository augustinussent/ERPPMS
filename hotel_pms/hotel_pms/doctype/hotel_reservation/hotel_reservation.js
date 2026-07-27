frappe.ui.form.on("Hotel Reservation", {
  refresh(frm) {
    if (frm.doc.docstatus === 1 && ["Confirmed", "Tentative"].includes(frm.doc.status)) {
      frm.add_custom_button(__("Check In"), () => {
        frappe.call({
          method: "hotel_pms.api.check_in",
          args: { reservation: frm.doc.name },
          freeze: true,
          callback: () => frm.reload_doc(),
        });
      }, __("Operations"));
    }
    if (frm.doc.docstatus === 1 && frm.doc.status === "Checked In") {
      frm.add_custom_button(__("Check Out"), () => {
        frappe.call({
          method: "hotel_pms.api.check_out",
          args: { reservation: frm.doc.name },
          freeze: true,
          callback: () => frm.reload_doc(),
        });
      }, __("Operations"));
    }
    if (frm.doc.folio) {
      frm.add_custom_button(__("Open Folio"), () => frappe.set_route("Form", "Hotel Folio", frm.doc.folio));
    }
  },
});
