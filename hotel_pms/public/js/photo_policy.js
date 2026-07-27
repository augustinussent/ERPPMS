frappe.provide("hotel_pms.photo_policy");

hotel_pms.photo_policy._enabled = null;

hotel_pms.photo_policy.get_enabled = async function () {
    if (hotel_pms.photo_policy._enabled !== null) {
        return hotel_pms.photo_policy._enabled;
    }
    const response = await frappe.call({ method: "hotel_pms.media.get_photo_policy" });
    hotel_pms.photo_policy._enabled = Boolean(response.message && response.message.enabled);
    return hotel_pms.photo_policy._enabled;
};

hotel_pms.photo_policy.apply = async function (frm, fieldnames, section_fieldname) {
    const enabled = await hotel_pms.photo_policy.get_enabled();
    for (const fieldname of fieldnames) {
        if (frm.fields_dict[fieldname]) {
            frm.set_df_property(fieldname, "hidden", !enabled);
        }
    }
    if (section_fieldname && frm.fields_dict[section_fieldname]) {
        frm.set_df_property(section_fieldname, "hidden", !enabled);
    }
    if (!enabled) {
        frm.dashboard.add_indicator(__("Photo evidence disabled by administrator"), "orange");
    }
};

frappe.ui.form.on("Hotel Housekeeping Task", {
    refresh(frm) {
        hotel_pms.photo_policy.apply(frm, ["before_photo", "after_photo"], "evidence_section");
    },
});

frappe.ui.form.on("Hotel Maintenance Ticket", {
    refresh(frm) {
        hotel_pms.photo_policy.apply(frm, ["before_photo", "after_photo"], "evidence_section");
    },
});

frappe.ui.form.on("Hotel PMS Settings", {
    refresh(frm) {
        hotel_pms.photo_policy._enabled = cint(frm.doc.enable_photo_uploads) === 1;
        frm.dashboard.add_indicator(
            frm.doc.enable_photo_uploads ? __("Photo uploads enabled") : __("Photo uploads disabled"),
            frm.doc.enable_photo_uploads ? "green" : "orange"
        );

        if (frappe.user_roles.includes("System Manager") || frappe.user_roles.includes("Hotel Manager")) {
            frm.add_custom_button(__("Check ERPNext Sync"), async () => {
                const response = await frappe.call({ method: "hotel_pms.reconcile.get_sync_health" });
                const health = response.message || {};
                frappe.msgprint({
                    title: health.healthy ? __("Synchronization Healthy") : __("Synchronization Review Required"),
                    indicator: health.healthy ? "green" : "orange",
                    message: `<p>${frappe.utils.escape_html(health.message || "")}</p>
                        <p>${__("Stale operations")}: ${(health.stale_in_progress_logs || []).length}<br>
                        ${__("Broken targets")}: ${(health.broken_sync_targets || []).length}<br>
                        ${__("Unlinked folio rows")}: ${health.invoiced_folio_rows_without_invoice || 0}<br>
                        ${__("Unlinked group rows")}: ${health.invoiced_group_rows_without_invoice || 0}</p>`,
                });
            }, __("ERPNext Sync"));

            frm.add_custom_button(__("Reconcile Existing Links"), async () => {
                const response = await frappe.call({ method: "hotel_pms.reconcile.run_reconciliation" });
                frappe.show_alert({
                    message: __("Reconciliation completed. Links repaired: {0}", [response.message.repaired || 0]),
                    indicator: "green",
                });
            }, __("ERPNext Sync"));
        }
    },
    enable_photo_uploads(frm) {
        hotel_pms.photo_policy._enabled = cint(frm.doc.enable_photo_uploads) === 1;
    },
});

frappe.realtime.on("hotel_pms_photo_policy_changed", (data) => {
    hotel_pms.photo_policy._enabled = Boolean(data && data.enabled);
});

frappe.ui.form.on("Hotel Room Inspection", {
    refresh(frm) {
        hotel_pms.photo_policy.apply(frm, ["inspection_photo"], null);
    },
});

frappe.ui.form.on("Hotel Lost and Found", {
    refresh(frm) {
        hotel_pms.photo_policy.apply(frm, ["item_photo"], "item_section");
    },
});

frappe.ui.form.on("Hotel SOP Candidate", {
    refresh(frm) {
        hotel_pms.photo_policy.apply(frm, ["before_photo", "after_photo", "reference_photo"], "evidence_section");
    },
});

hotel_pms.photo_policy.apply_child = async function (frm, table_fieldname, child_fieldnames) {
    const enabled = await hotel_pms.photo_policy.get_enabled();
    const grid = frm.fields_dict[table_fieldname] && frm.fields_dict[table_fieldname].grid;
    if (!grid) return;
    for (const fieldname of child_fieldnames) {
        grid.update_docfield_property(fieldname, "hidden", !enabled);
    }
    grid.refresh();
};

frappe.ui.form.on("Hotel Housekeeping Task", {
    refresh(frm) {
        hotel_pms.photo_policy.apply_child(frm, "checklist_items", ["photo"]);
    },
});

frappe.ui.form.on("Hotel Room Inspection", {
    refresh(frm) {
        hotel_pms.photo_policy.apply_child(frm, "items", ["photo"]);
    },
});

frappe.ui.form.on("Hotel Lost and Found", {
    refresh(frm) {
        hotel_pms.photo_policy.apply_child(frm, "custody_logs", ["handover_photo"]);
    },
});
