frappe.pages["hotel-restaurant-control"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Restaurant Control"), single_column: true });
  const property = page.add_field({ label: __("Property"), fieldtype: "Link", options: "Hotel Property", fieldname: "property", reqd: 1, change: load });
  const outlet = page.add_field({ label: __("Outlet"), fieldtype: "Link", options: "Hotel Outlet", fieldname: "outlet", get_query: () => ({ filters: { property: property.get_value() } }), change: load });
  page.add_inner_button(__("Refresh"), load);
  const body = $(`<div><style>.hrc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}.hrc-card{border:1px solid var(--border-color);border-radius:8px;padding:12px}.hrc-table{width:100%;margin:14px 0}.hrc-table th,.hrc-table td{padding:7px;border-bottom:1px solid var(--border-color);vertical-align:top}.hrc-bad{color:var(--red-600);font-weight:600}</style><div class="hrc-grid"></div><div class="hrc-detail"></div></div>`).appendTo(page.main);
  const e = value => frappe.utils.escape_html(String(value ?? ""));
  body.on("click", "[data-doc]", function () { frappe.set_route("Form", $(this).data("doctype"), $(this).data("doc")); });
  async function load() {
    const prop = property.get_value(); if (!prop) return;
    const response = await frappe.call({ method: "hotel_pms.restaurant_controls.get_restaurant_control_dashboard", args: { property: prop, outlet: outlet.get_value() || null } });
    const data = response.message || {};
    body.find(".hrc-grid").html((data.outlets || []).map(row => `<div class="hrc-card"><h4>${e(row.outlet_name || row.name)}</h4><p>${row.require_pos_opening_entry ? __("ERPNext POS session required") : __("Hotel shift only")}</p><small>${e(row.pos_profile || __("POS Profile missing"))}<br>${__("Cashier discount limit")}: ${e(row.cashier_discount_limit || 0)}%</small></div>`).join("") || `<div class="text-muted">${__("No enabled outlets")}</div>`);
    const table = (title, rows, columns) => `<h4>${title}</h4><table class="hrc-table"><thead><tr>${columns.map(c => `<th>${c[0]}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr data-doc="${e(r.name)}" data-doctype="${e(columns[0][2])}">${columns.map(c => `<td class="${c[3] && c[3](r) ? 'hrc-bad' : ''}">${e(r[c[1]])}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="${columns.length}">${__("None")}</td></tr>`}</tbody></table>`;
    body.find(".hrc-detail").html(
      table(__("Cashier Sessions"), data.shifts || [], [[__("Shift"),"name","Hotel Cashier Shift"],[__("Outlet"),"outlet"],[__("Cashier"),"cashier"],[__("Hotel Status"),"status"],[__("ERPNext Session"),"erpnext_session_status",null,r=>r.erpnext_session_status==='Mismatch'||r.erpnext_session_status==='Not Linked']]) +
      table(__("Kitchen Revisions"), data.tickets || [], [[__("KOT"),"name","Hotel Kitchen Ticket"],[__("Order"),"restaurant_order"],[__("Type"),"ticket_type"],[__("Revision"),"revision_no"],[__("Status"),"status"],[__("Stock"),"stock_posting_status",null,r=>r.stock_posting_status==='Failed']]) +
      table(__("Operational Alerts"), data.alerts || [], [[__("Alert"),"name","Hotel Restaurant Alert"],[__("Severity"),"severity",null,r=>r.severity==='High'||r.severity==='Critical'],[__("Type"),"alert_type"],[__("Message"),"message"]]) +
      table(__("Print Queue"), data.print_jobs || [], [[__("Job"),"name","Hotel Restaurant Print Job"],[__("Purpose"),"purpose"],[__("Reference"),"reference_name"],[__("Status"),"status",null,r=>r.status==='Failed'||r.status==='Dead Letter'],[__("Attempts"),"attempts"]])
    );
  }
  frappe.db.get_single_value("Hotel PMS Settings", "default_property").then(value => { if (value) property.set_value(value); });
};
