frappe.ui.form.on("Hotel Group Booking", {
    setup(frm) {
        frm.set_query("room_type", "room_blocks", () => ({ filters: { property: frm.doc.property, enabled: 1 } }));
        frm.set_query("room_type", "participants", () => ({ filters: { property: frm.doc.property, enabled: 1 } }));
        frm.set_query("assigned_room", "participants", (doc, cdt, cdn) => {
            const row = locals[cdt][cdn];
            return {
                filters: {
                    property: frm.doc.property,
                    room_type: row.room_type,
                    enabled: 1,
                    operational_status: ["not in", ["Out of Order", "Out of Service"]]
                }
            };
        });
        frm.set_query("function_space", "event_functions", () => ({ filters: { property: frm.doc.property, enabled: 1 } }));
        frm.set_query("package_template", "packages", () => ({ filters: { property: frm.doc.property, enabled: 1 } }));
    },

    refresh(frm) {
        if (frm.is_new()) return;

        frm.add_custom_button(__("Check Availability"), () => {
            frappe.call({
                method: "hotel_pms.group_booking.check_group_availability",
                args: { group_booking: frm.doc.name },
                freeze: true,
                callback(r) {
                    const rows = (r.message.rooms || []).map(row =>
                        `${row.room_type}: ${row.requested} requested / ${row.available} available`
                    );
                    frappe.msgprint([r.message.message, ...rows].join("<br>"));
                }
            });
        }, __("Group Booking"));

        frm.add_custom_button(__("Create Quotation"), () => call_and_route(
            frm,
            "hotel_pms.group_booking.create_group_quotation",
            "quotation",
            "Quotation"
        ), __("Commercial"));

        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__("Create Sales Order"), () => call_and_route(
                frm,
                "hotel_pms.group_booking.create_group_sales_order",
                "sales_order",
                "Sales Order"
            ), __("Commercial"));

            frm.add_custom_button(__("Create Participant Reservations"), () => {
                frappe.call({
                    method: "hotel_pms.group_booking.create_participant_reservations",
                    args: { group_booking: frm.doc.name },
                    freeze: true,
                    callback(r) {
                        frappe.msgprint(__("Created {0} reservation(s).", [r.message.created_count]));
                        frm.reload_doc();
                    }
                });
            }, __("Operations"));

            frm.add_custom_button(__("Generate Package Schedule"), () => {
                frappe.call({
                    method: "hotel_pms.group_booking.generate_package_schedule",
                    args: { group_booking: frm.doc.name },
                    freeze: true,
                    callback(r) {
                        frappe.msgprint(__("Created {0} posting(s); skipped {1} existing posting(s).", [r.message.created, r.message.skipped]));
                    }
                });
            }, __("Operations"));

            frm.add_custom_button(__("Post Due Package Charges"), () => {
                frappe.call({
                    method: "hotel_pms.group_booking.post_package_schedule",
                    args: { group_booking: frm.doc.name },
                    freeze: true,
                    callback(r) {
                        frappe.msgprint(__("Posted {0} charge(s) to {1}.", [r.message.posted, r.message.group_folio]));
                        frm.reload_doc();
                    }
                });
            }, __("Operations"));
        }

        frm.add_custom_button(__("Create BEO Revision"), () => call_and_route(
            frm,
            "hotel_pms.group_booking.create_beo",
            "beo",
            "Hotel Banquet Event Order"
        ), __("Documents"));

        frm.add_custom_button(__("Confirmation Letter"), () => {
            const format = encodeURIComponent("Hotel Group Confirmation Letter");
            const doctype = encodeURIComponent(frm.doc.doctype);
            const name = encodeURIComponent(frm.doc.name);
            window.open(`/printview?doctype=${doctype}&name=${name}&format=${format}&no_letterhead=0`, "_blank");
        }, __("Documents"));

        frm.add_custom_button(__("Confirmation Letter PDF"), () => {
            const format = encodeURIComponent("Hotel Group Confirmation Letter");
            const doctype = encodeURIComponent(frm.doc.doctype);
            const name = encodeURIComponent(frm.doc.name);
            window.open(`/api/method/frappe.utils.print_format.download_pdf?doctype=${doctype}&name=${name}&format=${format}&no_letterhead=0`, "_blank");
        }, __("Documents"));

        if (frm.doc.group_folio) {
            frm.add_custom_button(__("Open Group Folio"), () => frappe.set_route("Form", "Hotel Group Folio", frm.doc.group_folio), __("Billing"));
        } else {
            frm.add_custom_button(__("Create Group Folio"), () => call_and_route(
                frm,
                "hotel_pms.group_booking.ensure_group_folio",
                "group_folio",
                "Hotel Group Folio"
            ), __("Billing"));
        }
    }
});

frappe.ui.form.on("Hotel Group Package", {
    package_template(frm, cdt, cdn) { fetch_package_rate(frm, cdt, cdn); },
    occupancy_type(frm, cdt, cdn) { fetch_package_rate(frm, cdt, cdn); },
    guaranteed_pax(frm, cdt, cdn) { fetch_package_rate(frm, cdt, cdn); }
});

function fetch_package_rate(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.package_template) return;
    frappe.call({
        method: "hotel_pms.group_booking.get_package_rate",
        args: {
            package_template: row.package_template,
            occupancy_type: row.occupancy_type || "Any",
            pricing_basis: row.pricing_basis || null,
            pax: row.guaranteed_pax || row.estimated_pax || frm.doc.guaranteed_pax || frm.doc.estimated_pax || 0
        },
        callback(r) {
            if (!r.message) return;
            frappe.model.set_value(cdt, cdn, "pricing_basis", r.message.pricing_basis);
            frappe.model.set_value(cdt, cdn, "unit_rate", r.message.rate);
        }
    });
}

function call_and_route(frm, method, responseKey, doctype) {
    frappe.call({
        method,
        args: { group_booking: frm.doc.name },
        freeze: true,
        callback(r) {
            const name = r.message && r.message[responseKey];
            if (name) frappe.set_route("Form", doctype, name);
            frm.reload_doc();
        }
    });
}
