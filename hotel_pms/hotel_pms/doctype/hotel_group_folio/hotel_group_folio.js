frappe.ui.form.on("Hotel Group Folio", {
    refresh(frm) {
        if (frm.is_new()) return;
        frm.add_custom_button(__("Create Sales Invoice(s)"), () => {
            frappe.call({
                method: "hotel_pms.group_booking.create_group_sales_invoices",
                args: { group_folio: frm.doc.name },
                freeze: true,
                callback(r) {
                    frappe.msgprint(__("Created {0} Sales Invoice(s): {1}", [r.message.count, r.message.sales_invoices.join(", ")]));
                    frm.reload_doc();
                }
            });
        });
    }
});
