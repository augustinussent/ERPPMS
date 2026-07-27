frappe.ui.form.on("Hotel Guest Registration", {
  refresh(frm) {
    hotel_pms.photo_policy.apply(frm, ["id_file"]);
    if (!frm.is_new()) {
      frm.add_custom_button(__("Print Registration Card"), () => {
        const url = frappe.urllib.get_full_url(`/printview?doctype=Hotel%20Guest%20Registration&name=${encodeURIComponent(frm.doc.name)}&format=Hotel%20Guest%20Registration%20Card&no_letterhead=0`);
        window.open(url, "_blank");
      });
    }
  },
});
