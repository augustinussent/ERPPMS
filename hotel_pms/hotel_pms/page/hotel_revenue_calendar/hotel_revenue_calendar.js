frappe.pages["hotel-revenue-calendar"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Hotel Revenue Calendar"), single_column: true });
  const state = { rows: [], property: null, room_type: null, rate_plan: null, start_date: frappe.datetime.get_today() };
  const property = page.add_field({ label: __("Property"), fieldtype: "Link", fieldname: "property", options: "Hotel Property", reqd: 1, change: load });
  const roomType = page.add_field({ label: __("Room Type"), fieldtype: "Link", fieldname: "room_type", options: "Hotel Room Type", reqd: 1, get_query: () => ({ filters: { property: property.get_value(), enabled: 1 } }), change: load });
  const ratePlan = page.add_field({ label: __("Rate Plan"), fieldtype: "Link", fieldname: "rate_plan", options: "Hotel Rate Plan", reqd: 1, get_query: () => ({ filters: { property: property.get_value(), room_type: roomType.get_value(), enabled: 1 } }), change: load });
  const startDate = page.add_field({ label: __("Start Date"), fieldtype: "Date", fieldname: "start_date", default: state.start_date, change: load });
  const days = page.add_field({ label: __("Days"), fieldtype: "Int", fieldname: "days", default: 31, change: load });
  page.set_primary_action(__("Save Changes"), save, "save");
  page.add_inner_button(__("Refresh"), load);
  page.add_inner_button(__("Front Desk"), () => frappe.set_route("hotel-front-desk"));
  const body = $("<div class='hotel-rate-calendar'></div>").appendTo(page.main);

  function esc(v) { return frappe.utils.escape_html(String(v == null ? "" : v)); }
  function checked(v) { return Number(v) ? "checked" : ""; }
  function render() {
    body.html(`<style>
      .hrc-wrap{overflow:auto;border:1px solid var(--border-color);border-radius:8px;margin-top:12px}
      .hrc-table{width:100%;min-width:1300px;border-collapse:collapse}.hrc-table th,.hrc-table td{padding:6px;border-bottom:1px solid var(--border-color);white-space:nowrap}
      .hrc-table input[type=number]{width:110px}.hrc-table input[type=checkbox]{transform:scale(1.1)}.hrc-error{color:var(--red-500);font-size:11px}
    </style><div class="hrc-wrap"><table class="hrc-table"><thead><tr>
      <th>${__("Date")}</th><th>${__("Effective")}</th><th>${__("Override")}</th><th>${__("Floor")}</th>
      <th>${__("Min Stay")}</th><th>${__("Max Stay")}</th><th>${__("CTA")}</th><th>${__("CTD")}</th><th>${__("Stop Sell")}</th>
      <th>${__("Min Advance")}</th><th>${__("Max Advance")}</th><th>${__("Notes")}</th>
    </tr></thead><tbody>${state.rows.map((r, i) => `<tr data-index="${i}">
      <td>${esc(frappe.datetime.str_to_user(r.date))}${r.error ? `<div class="hrc-error">${esc(r.error)}</div>` : ""}</td>
      <td>${r.effective_rate == null ? "-" : format_currency(r.effective_rate)}</td>
      <td><input class="form-control input-xs" data-field="rate_override" type="number" step="0.01" value="${esc(r.rate_override || "")}"></td>
      <td><input class="form-control input-xs" data-field="floor_rate" type="number" step="0.01" value="${esc(r.floor_rate || "")}"></td>
      <td><input class="form-control input-xs" data-field="minimum_stay" type="number" value="${esc(r.minimum_stay || "")}"></td>
      <td><input class="form-control input-xs" data-field="maximum_stay" type="number" value="${esc(r.maximum_stay || "")}"></td>
      <td class="text-center"><input data-field="closed_to_arrival" type="checkbox" ${checked(r.closed_to_arrival)}></td>
      <td class="text-center"><input data-field="closed_to_departure" type="checkbox" ${checked(r.closed_to_departure)}></td>
      <td class="text-center"><input data-field="stop_sell" type="checkbox" ${checked(r.stop_sell)}></td>
      <td><input class="form-control input-xs" data-field="minimum_advance_days" type="number" value="${esc(r.minimum_advance_days || "")}"></td>
      <td><input class="form-control input-xs" data-field="maximum_advance_days" type="number" value="${esc(r.maximum_advance_days || "")}"></td>
      <td><input class="form-control input-xs" data-field="notes" value="${esc(r.notes || "")}"></td>
    </tr>`).join("")}</tbody></table></div>`);
  }

  body.on("change", "[data-field]", function () {
    const tr = $(this).closest("tr"); const row = state.rows[Number(tr.data("index"))]; const field = $(this).data("field");
    row[field] = $(this).attr("type") === "checkbox" ? ($(this).is(":checked") ? 1 : 0) : $(this).val();
    row._changed = true;
  });

  async function load() {
    state.property = property.get_value(); state.room_type = roomType.get_value(); state.rate_plan = ratePlan.get_value(); state.start_date = startDate.get_value();
    if (!state.property || !state.room_type || !state.rate_plan) return;
    const response = await frappe.call({ method: "hotel_pms.revenue.get_rate_calendar", args: { property: state.property, room_type: state.room_type, rate_plan: state.rate_plan, start_date: state.start_date, days: days.get_value() || 31 }, freeze: true });
    state.rows = response.message.days || []; render();
  }

  async function save() {
    if (!state.property || !state.room_type || !state.rate_plan) return frappe.msgprint(__("Select property, room type, and rate plan."));
    const rows = state.rows.filter(r => r._changed).map(r => ({ ...r, error: undefined, effective_rate: undefined, _changed: undefined }));
    if (!rows.length) return frappe.show_alert({ message: __("No changes to save."), indicator: "blue" });
    await frappe.call({ method: "hotel_pms.revenue.bulk_upsert_rate_calendar", args: { payload: { property: state.property, room_type: state.room_type, rate_plan: state.rate_plan, rows } }, freeze: true });
    frappe.show_alert({ message: __("Rate calendar saved."), indicator: "green" }); await load();
  }

  frappe.db.get_single_value("Hotel PMS Settings", "default_property").then(v => { if (v) property.set_value(v); });
};
