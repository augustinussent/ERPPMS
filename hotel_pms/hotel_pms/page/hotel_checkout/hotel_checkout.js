frappe.pages["hotel-checkout"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Hotel Checkout"), single_column: true });
  const reservation = page.add_field({ label: __("Reservation"), fieldtype: "Link", fieldname: "reservation", options: "Hotel Reservation", reqd: 1, change: load });
  page.add_inner_button(__("Refresh"), load);
  page.add_inner_button(__("Front Desk"), () => frappe.set_route("hotel-front-desk"));
  const body = $("<div class='hotel-checkout-page'></div>").appendTo(page.main);
  let data = null;
  function esc(v) { return frappe.utils.escape_html(String(v == null ? "" : v)); }

  function render() {
    if (!data) return;
    const active = data.charges.filter(x => !x.is_void);
    body.html(`<style>
      .hco-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:12px 0}.hco-card{border:1px solid var(--border-color);border-radius:8px;padding:12px;background:var(--card-bg)}
      .hco-card b{display:block;font-size:20px}.hco-table{width:100%;border-collapse:collapse}.hco-table th,.hco-table td{padding:7px;border-bottom:1px solid var(--border-color)}.hco-actions button{margin:3px}
    </style>
    <div class="hco-grid">
      <div class="hco-card">${__("Active Charges")}<b>${format_currency(data.totals.active_charges)}</b></div>
      <div class="hco-card">${__("Uninvoiced")}<b>${format_currency(data.totals.uninvoiced)}</b></div>
      <div class="hco-card">${__("Invoice Outstanding")}<b>${format_currency(data.totals.invoice_outstanding)}</b></div>
      <div class="hco-card">${__("Available Deposit")}<b>${format_currency(data.deposit.available_credit || 0)}</b></div>
      <div class="hco-card">${__("Net Due")}<b>${format_currency(data.totals.net_due_after_available_deposit)}</b></div>
    </div>
    <div class="hco-actions">
      <button class="btn btn-primary" data-action="invoice">${__("Create Invoice")}</button>
      <button class="btn btn-default" data-action="transfer">${__("Transfer Selected Charges")}</button>
      <button class="btn btn-default" data-action="directbill">${__("Request Direct Bill")}</button>
      ${data.reservation.status === "Checked In" ? `<button class="btn btn-danger" data-action="checkout">${__("Complete Checkout")}</button>` : ""}
    </div>
    <h4>${__("Charges")}</h4><table class="hco-table"><thead><tr><th></th><th>${__("Date")}</th><th>${__("Description")}</th><th>${__("Amount")}</th><th>${__("Invoice")}</th></tr></thead><tbody>
      ${active.map(x => `<tr><td><input type="checkbox" data-charge="${esc(x.row)}" ${x.sales_invoice ? "disabled" : ""}></td><td>${esc(x.posting_date)}</td><td>${esc(x.description)}</td><td>${format_currency(x.amount)}</td><td>${x.sales_invoice ? `<a href="/app/sales-invoice/${esc(x.sales_invoice)}">${esc(x.sales_invoice)}</a>` : "-"}</td></tr>`).join("") || `<tr><td colspan="5">${__("No active charges")}</td></tr>`}
    </tbody></table>
    <h4>${__("Invoices & Payment Requests")}</h4><table class="hco-table"><thead><tr><th>${__("Invoice")}</th><th>${__("Total")}</th><th>${__("Outstanding")}</th><th>${__("Payment Request")}</th></tr></thead><tbody>
      ${data.invoices.map(inv => { const pr = data.payment_requests.find(x => x.reference_name === inv.name); return `<tr><td><a href="/app/sales-invoice/${esc(inv.name)}">${esc(inv.name)}</a></td><td>${format_currency(inv.grand_total)}</td><td>${format_currency(inv.outstanding_amount)}</td><td>${pr ? `<a href="/app/payment-request/${esc(pr.name)}">${esc(pr.status)}</a>` : `<button class="btn btn-xs btn-default" data-payreq="${esc(inv.name)}">${__("Create Link")}</button>`}</td></tr>`; }).join("") || `<tr><td colspan="4">${__("No invoices")}</td></tr>`}
    </tbody></table>`);
  }

  body.on("click", "[data-action=invoice]", async () => {
    if (!data.folio) return frappe.msgprint(__("No folio exists."));
    const r = await frappe.call({ method: "hotel_pms.api.create_sales_invoice", args: { folio: data.folio }, freeze: true });
    frappe.set_route("Form", "Sales Invoice", r.message.sales_invoice);
  });
  body.on("click", "[data-payreq]", function () { paymentRequestDialog($(this).data("payreq")); });
  body.on("click", "[data-action=checkout]", async () => { await frappe.call({ method: "hotel_pms.api.check_out", args: { reservation: reservation.get_value() }, freeze: true }); await load(); });
  body.on("click", "[data-action=transfer]", transferDialog);
  body.on("click", "[data-action=directbill]", directBillDialog);

  function selectedRows() { return body.find("[data-charge]:checked").map((_, x) => $(x).data("charge")).get(); }
  function transferDialog() {
    const rows = selectedRows(); if (!rows.length) return frappe.msgprint(__("Select one or more uninvoiced charges."));
    const d = new frappe.ui.Dialog({ title: __("Transfer Charges"), fields: [
      { fieldname: "destination_folio_type", label: __("Destination Type"), fieldtype: "Select", options: "Hotel Folio\nHotel Group Folio\nHotel City Ledger Folio", reqd: 1 },
      { fieldname: "destination_folio", label: __("Destination Folio"), fieldtype: "Dynamic Link", options: "destination_folio_type", reqd: 1 },
      { fieldname: "percentage", label: __("Percentage per Line"), fieldtype: "Percent", default: 100, reqd: 1 },
      { fieldname: "reason", label: __("Audit Reason"), fieldtype: "Small Text", reqd: 1 },
    ], primary_action_label: __("Transfer"), primary_action: async values => {
      const payload = { source_folio_type: "Hotel Folio", source_folio: data.folio, ...values, request_key: `WEB-${Date.now()}`, lines: rows.map(row => ({ source_charge_row: row, percentage: values.percentage })) };
      await frappe.call({ method: "hotel_pms.billing.transfer_folio_charges", args: { payload }, freeze: true }); d.hide(); await load();
    }}); d.show();
  }
  function paymentRequestDialog(invoice) {
    const d = new frappe.ui.Dialog({ title: __("Create Payment Request"), fields: [
      { fieldname: "recipient_email", label: __("Recipient Email"), fieldtype: "Data", options: "Email" },
      { fieldname: "payment_gateway_account", label: __("Payment Gateway Account"), fieldtype: "Link", options: "Payment Gateway Account" },
      { fieldname: "submit", label: __("Submit and Generate Link"), fieldtype: "Check", default: 0 },
    ], primary_action_label: __("Create"), primary_action: async values => {
      const r = await frappe.call({ method: "hotel_pms.billing.create_payment_request_for_invoice", args: { sales_invoice: invoice, ...values }, freeze: true }); d.hide();
      frappe.set_route("Form", "Payment Request", r.message.payment_request);
    }}); d.show();
  }
  function directBillDialog() {
    const d = new frappe.ui.Dialog({ title: __("Request Direct Bill"), fields: [
      { fieldname: "city_ledger_account", label: __("City Ledger Account"), fieldtype: "Link", options: "Hotel City Ledger Account", reqd: 1, get_query: () => ({ filters: { property: data.reservation.property, status: "Active" } }) },
      { fieldname: "amount", label: __("Requested Amount"), fieldtype: "Currency", default: data.totals.net_due_after_available_deposit, reqd: 1 },
      { fieldname: "reason", label: __("Reason"), fieldtype: "Small Text", reqd: 1 },
    ], primary_action_label: __("Request Approval"), primary_action: async values => {
      const r = await frappe.call({ method: "hotel_pms.billing.request_direct_bill_approval", args: { reservation: data.reservation.name, ...values, request_key: `WEB-${Date.now()}` }, freeze: true }); d.hide();
      frappe.set_route("Form", "Hotel Direct Bill Approval", r.message.approval);
    }}); d.show();
  }
  async function load() {
    if (!reservation.get_value()) return;
    const r = await frappe.call({ method: "hotel_pms.billing.get_checkout_summary", args: { reservation: reservation.get_value() }, freeze: true }); data = r.message; render();
  }
  if (frappe.route_options && frappe.route_options.reservation) {
    reservation.set_value(frappe.route_options.reservation);
    frappe.route_options = null;
  }
};
