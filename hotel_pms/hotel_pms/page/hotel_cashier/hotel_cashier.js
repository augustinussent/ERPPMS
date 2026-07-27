frappe.pages["hotel-cashier"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Hotel Cashier"), single_column: true });
  const property = page.add_field({ label: __("Property"), fieldtype: "Link", fieldname: "property", options: "Hotel Property", reqd: 1 });
  const shift = page.add_field({ label: __("Cashier Shift"), fieldtype: "Link", fieldname: "cashier_shift", options: "Hotel Cashier Shift", get_query: () => ({ filters: { property: property.get_value(), status: ["in", ["Open", "Closing Review"]] } }), change: load });
  page.set_primary_action(__("Open Shift"), openShift, "add"); page.add_inner_button(__("Refresh"), load);
  const body = $("<div class='hotel-cashier-page'></div>").appendTo(page.main); let data = null;
  function esc(v) { return frappe.utils.escape_html(String(v == null ? "" : v)); }
  function render() {
    if (!data) return body.html(`<div class="text-muted">${__("Open or select a cashier shift.")}</div>`);
    const s = data.shift, t = data.totals;
    body.html(`<style>.hc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:12px 0}.hc-card{border:1px solid var(--border-color);padding:12px;border-radius:8px}.hc-card b{font-size:20px;display:block}.hc-table{width:100%;border-collapse:collapse}.hc-table th,.hc-table td{padding:6px;border-bottom:1px solid var(--border-color)}.hc-actions button{margin:3px}</style>
      <div class="hc-grid"><div class="hc-card">${__("Opening Float")}<b>${format_currency(s.opening_float)}</b></div><div class="hc-card">${__("Receipts")}<b>${format_currency(t.cash_receipts)}</b></div><div class="hc-card">${__("Refunds")}<b>${format_currency(t.cash_refunds)}</b></div><div class="hc-card">${__("Adjustments")}<b>${format_currency(t.drawer_adjustments)}</b></div><div class="hc-card">${__("Expected Cash")}<b>${format_currency(t.expected_cash)}</b></div></div>
      <div class="hc-actions"><button class="btn btn-default" data-action="movement">${__("Drawer Movement")}</button><button class="btn btn-danger" data-action="close">${__("Close Shift")}</button></div>
      <h4>${__("Payment Entries")}</h4><table class="hc-table"><thead><tr><th>${__("Document")}</th><th>${__("Type")}</th><th>${__("Party")}</th><th>${__("Amount")}</th></tr></thead><tbody>${data.payment_entries.map(x => `<tr><td><a href="/app/payment-entry/${esc(x.name)}">${esc(x.name)}</a></td><td>${esc(x.payment_type)}</td><td>${esc(x.party)}</td><td>${format_currency(x.payment_type === "Receive" ? x.received_amount : x.paid_amount)}</td></tr>`).join("") || `<tr><td colspan="4">${__("No payments")}</td></tr>`}</tbody></table>`);
  }
  body.on("click", "[data-action=movement]", movementDialog); body.on("click", "[data-action=close]", closeDialog);
  function openShift() {
    if (!property.get_value()) return frappe.msgprint(__("Select a property."));
    const d = new frappe.ui.Dialog({ title: __("Open Cashier Shift"), fields: [
      { fieldname: "mode_of_payment", label: __("Cash Mode of Payment"), fieldtype: "Link", options: "Mode of Payment", reqd: 1 },
      { fieldname: "opening_float", label: __("Opening Float"), fieldtype: "Currency", default: 0 },
    ], primary_action_label: __("Open"), primary_action: async values => { const r = await frappe.call({ method: "hotel_pms.billing.open_cashier_shift", args: { property: property.get_value(), ...values, request_key: `WEB-${Date.now()}` }, freeze: true }); d.hide(); shift.set_value(r.message.cashier_shift); }}); d.show();
  }
  function movementDialog() {
    const d = new frappe.ui.Dialog({ title: __("Drawer Movement"), fields: [
      { fieldname: "movement_type", label: __("Type"), fieldtype: "Select", options: "Float In\nFloat Out\nPaid Out\nCorrection In\nCorrection Out", reqd: 1 },
      { fieldname: "amount", label: __("Amount"), fieldtype: "Currency", reqd: 1 },
      { fieldname: "reason", label: __("Reason"), fieldtype: "Small Text", reqd: 1 },
    ], primary_action_label: __("Record"), primary_action: async values => { await frappe.call({ method: "hotel_pms.billing.record_cashier_movement", args: { shift: shift.get_value(), ...values, request_key: `WEB-${Date.now()}` }, freeze: true }); d.hide(); await load(); }}); d.show();
  }
  function closeDialog() {
    const d = new frappe.ui.Dialog({ title: __("Close Cashier Shift"), fields: [
      { fieldname: "counted_cash", label: __("Counted Cash"), fieldtype: "Currency", reqd: 1 },
      { fieldname: "variance_reason", label: __("Variance Reason"), fieldtype: "Small Text" },
    ], primary_action_label: __("Close"), primary_action: async values => { await frappe.call({ method: "hotel_pms.billing.close_cashier_shift", args: { shift: shift.get_value(), ...values }, freeze: true }); d.hide(); data = null; render(); }}); d.show();
  }
  async function load() { if (!shift.get_value()) return; const r = await frappe.call({ method: "hotel_pms.billing.get_cashier_shift_summary", args: { shift: shift.get_value() }, freeze: true }); data = r.message; render(); }
  if (frappe.route_options && frappe.route_options.cashier_shift) {
    const routeShift = frappe.route_options.cashier_shift;
    frappe.route_options = null;
    frappe.db.get_value("Hotel Cashier Shift", routeShift, "property").then(r => {
      if (r && r.message && r.message.property) property.set_value(r.message.property);
      shift.set_value(routeShift);
    });
  } else {
    frappe.db.get_single_value("Hotel PMS Settings", "default_property").then(v => { if (v) property.set_value(v); });
  }
};
