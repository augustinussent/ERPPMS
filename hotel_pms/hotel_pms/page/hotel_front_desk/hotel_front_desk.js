frappe.pages["hotel-front-desk"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Hotel Front Desk"), single_column: true });
  page.main.addClass("hotel-front-desk-page");
  const state = { property: null, date: frappe.datetime.get_today(), days: 14 };

  const propertyField = page.add_field({
    label: __("Property"), fieldtype: "Link", fieldname: "property", options: "Hotel Property", reqd: 1,
    change() { state.property = propertyField.get_value(); refreshAll(); },
  });
  const dateField = page.add_field({
    label: __("Business Date"), fieldtype: "Date", fieldname: "business_date", default: state.date,
    change() { state.date = dateField.get_value(); refreshAll(); },
  });
  page.set_primary_action(__("Quick Booking"), () => quickBooking(), "add");
  page.add_inner_button(__("Refresh"), () => refreshAll());
  page.add_inner_button(__("Operations Mobile"), () => frappe.set_route("hotel-housekeeping-mobile"));
  page.add_inner_button(__("Revenue Calendar"), () => frappe.set_route("hotel-revenue-calendar"));
  page.add_inner_button(__("Cashier"), () => frappe.set_route("hotel-cashier"));

  const body = $(`<div>
    <style>
      .hfd-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:12px 0}
      .hfd-card{background:var(--card-bg);border:1px solid var(--border-color);border-radius:8px;padding:14px}
      .hfd-card b{font-size:24px;display:block}.hfd-section{margin-top:18px}
      .hfd-list{width:100%;border-collapse:collapse}.hfd-list th,.hfd-list td{padding:8px;border-bottom:1px solid var(--border-color);vertical-align:middle}
      .hfd-actions button{margin-right:6px}.hfd-tape-wrap{overflow:auto;border:1px solid var(--border-color);border-radius:8px}
      .hfd-tape{min-width:1100px}.hfd-tape-row{display:grid;grid-template-columns:170px repeat(var(--days), minmax(78px,1fr));min-height:42px;position:relative}
      .hfd-tape-row>div{border-right:1px solid var(--border-color);border-bottom:1px solid var(--border-color);padding:7px}
      .hfd-room{position:sticky;left:0;background:var(--card-bg);z-index:3}.hfd-bar{position:absolute;top:5px;height:31px;border-radius:5px;padding:6px 8px;overflow:hidden;white-space:nowrap;z-index:2;background:var(--blue-100);border:1px solid var(--blue-300);cursor:pointer}
      .hfd-bar.checked-in{background:var(--green-100);border-color:var(--green-300)}.hfd-bar.tentative{background:var(--yellow-100);border-color:var(--yellow-300)}
      .hfd-tabs{display:flex;gap:8px;margin:15px 0}.hfd-tabs button.active{font-weight:700}
    </style>
    <div class="hfd-summary"></div>
    <div class="hfd-tabs"><button class="btn btn-default active" data-tab="today">${__("Today")}</button><button class="btn btn-default" data-tab="tape">${__("Tape Chart")}</button></div>
    <div class="hfd-view hfd-today"></div><div class="hfd-view hfd-tape-view" style="display:none"></div>
  </div>`).appendTo(page.main);

  body.on("click", ".hfd-tabs button", function () {
    body.find(".hfd-tabs button").removeClass("active"); $(this).addClass("active");
    body.find(".hfd-view").hide(); body.find(`.hfd-${$(this).data("tab")}${$(this).data("tab") === "tape" ? "-view" : ""}`).show();
  });
  body.on("click", "[data-reservation]", function () { frappe.set_route("Form", "Hotel Reservation", $(this).data("reservation")); });
  body.on("click", "[data-action=checkin]", async function (event) { event.stopPropagation(); await openCheckin($(this).data("name")); });
  body.on("click", "[data-action=checkout]", function (event) {
    event.stopPropagation();
    frappe.route_options = { reservation: $(this).data("name") };
    frappe.set_route("hotel-checkout");
  });

  async function callOp(method, args) { await frappe.call({ method, args, freeze: true }); refreshAll(); }

  async function openCheckin(reservation) {
    const response = await frappe.call({ method: "hotel_pms.distribution.get_checkin_context", args: { reservation }, freeze: true });
    const ctx = response.message || {}; const ready = ctx.readiness || {}; const assigned = ctx.assigned_rooms || [];
    const options = (ctx.available_rooms || []).map(r => ({ label: `${r.room_number} · ${r.housekeeping_status}${r.floor ? ` · ${r.floor}` : ""}`, value: r.name }));
    assigned.forEach(r => { if (!options.some(x => x.value === r.name)) options.unshift({ label: `${r.room_number} · ${r.housekeeping_status}`, value: r.name }); });
    const defaultRoom = assigned[0]?.name || ctx.suggestion?.name || "";
    const chips = [
      [ready.registration_status === "Verified", `Registration: ${ready.registration_status || "Not Started"}`],
      [ready.id_on_file, __("ID on file")], [ready.address_on_file, __("Address proof")],
      [ready.prearrival_status === "Submitted", `Pre-arrival: ${ready.prearrival_status || "Not Issued"}`],
    ].map(([ok,label]) => `<span style="display:inline-block;margin:2px;padding:3px 8px;border-radius:12px;background:${ok ? "var(--green-100)" : "var(--gray-100)"}">${ok ? "✓" : "·"} ${esc(label)}</span>`).join("");
    const dialog = new frappe.ui.Dialog({ title: __("Check-in Readiness"), fields: [
      { fieldtype:"HTML", fieldname:"readiness", options:`<div style="margin-bottom:12px">${chips}</div>${ready.allergies ? `<div class="alert alert-warning"><b>${__("Allergies")}</b>: ${esc(ready.allergies)}</div>` : ""}${ready.accessibility_notes ? `<div class="alert alert-info"><b>${__("Accessibility")}</b>: ${esc(ready.accessibility_notes)}</div>` : ""}` },
      { fieldname:"room", label:__("Room"), fieldtype:"Select", options:options.map(x=>x.value).join("\n"), default:defaultRoom, reqd:1, description:ctx.suggestion ? `${__("Suggested")}: ${esc(ctx.suggestion.room_number)} · ${esc(ctx.suggestion.reason)}` : "" },
      { fieldtype:"HTML", fieldname:"room_labels", options:`<small>${options.map(x=>`${esc(x.value)} = ${esc(x.label)}`).join("<br>")}</small>` },
    ], primary_action_label:__("Confirm Check-in"), primary_action:async values=>{
      await frappe.call({ method:"hotel_pms.distribution.confirm_checkin", args:{ reservation, room:values.room }, freeze:true });
      dialog.hide(); refreshAll();
    }});
    dialog.show();
  }
  function esc(value) { return frappe.utils.escape_html(String(value == null ? "" : value)); }
  function money(value) { return format_currency(value || 0); }
  function roomNames(row) { return (row.rooms || []).map(x => x.room).join(", "); }

  function renderRows(title, rows, action) {
    return `<div class="hfd-section"><h4>${esc(title)}</h4><table class="hfd-list"><thead><tr><th>${__("Reservation")}</th><th>${__("Guest")}</th><th>${__("Room")}</th><th>${__("Status")}</th><th>${__("Balance")}</th><th></th></tr></thead><tbody>${rows.length ? rows.map(row => `<tr data-reservation="${esc(row.name)}"><td>${esc(row.name)}</td><td>${esc(row.guest)}</td><td>${esc(roomNames(row))}</td><td>${esc(row.status)}</td><td>${money(row.balance)}</td><td class="hfd-actions">${action ? `<button class="btn btn-xs btn-primary" data-action="${action}" data-name="${esc(row.name)}">${action === "checkin" ? __("Check In") : __("Check Out")}</button>` : ""}</td></tr>`).join("") : `<tr><td colspan="6" class="text-muted">${__("No records")}</td></tr>`}</tbody></table></div>`;
  }

  async function loadToday() {
    const response = await frappe.call({ method: "hotel_pms.front_desk.get_today_dashboard", args: { property: state.property, business_date: state.date } });
    const d = response.message;
    body.find(".hfd-summary").html([
      [__("Arrivals"), d.summary.arrivals], [__("Departures"), d.summary.departures], [__("In House"), d.summary.in_house], [__("No-show Review"), d.summary.no_show_candidates]
    ].map(x => `<div class="hfd-card"><span>${esc(x[0])}</span><b>${x[1]}</b></div>`).join(""));
    body.find(".hfd-today").html(renderRows(__("Arrivals"), d.arrivals, "checkin") + renderRows(__("Departures"), d.departures, "checkout") + renderRows(__("In House"), d.in_house));
  }

  async function loadTape() {
    const response = await frappe.call({ method: "hotel_pms.front_desk.get_tape_chart", args: { property: state.property, start_date: state.date, days: state.days } });
    const d = response.message, barsByRoom = {};
    d.bars.forEach(bar => (barsByRoom[bar.room] ||= []).push(bar));
    const header = `<div class="hfd-tape-row" style="--days:${d.dates.length}"><div class="hfd-room"><b>${__("Room")}</b></div>${d.dates.map(x => `<div><small>${esc(frappe.datetime.str_to_user(x))}</small></div>`).join("")}</div>`;
    const rows = d.rooms.map(room => {
      const bars = (barsByRoom[room.name] || []).map(bar => `<div class="hfd-bar ${esc(bar.status.toLowerCase().replaceAll(" ", "-"))}" data-reservation="${esc(bar.name)}" style="left:calc(170px + ${bar.start_index} * ((100% - 170px) / ${d.dates.length}));width:calc(${bar.span} * ((100% - 170px) / ${d.dates.length}) - 4px)">${esc(bar.guest)} · ${esc(bar.status)}</div>`).join("");
      return `<div class="hfd-tape-row" style="--days:${d.dates.length}"><div class="hfd-room"><b>${esc(room.room_number)}</b><br><small>${esc(room.room_type)} · ${esc(room.housekeeping_status)}</small></div>${d.dates.map(() => "<div></div>").join("")}${bars}</div>`;
    }).join("");
    body.find(".hfd-tape-view").html(`<div class="hfd-tape-wrap"><div class="hfd-tape">${header}${rows}</div></div>`);
  }

  async function quickBooking() {
    if (!state.property) return frappe.msgprint(__("Select a property first."));
    const dialog = new frappe.ui.Dialog({ title: __("Quick Multi-room Booking"), fields: [
      { fieldname:"guest", label:__("Guest Customer"), fieldtype:"Link", options:"Customer", reqd:1 },
      { fieldname:"billing_customer", label:__("Billing Customer"), fieldtype:"Link", options:"Customer" },
      { fieldname:"arrival_date", label:__("Arrival"), fieldtype:"Date", default:state.date, reqd:1 },
      { fieldname:"departure_date", label:__("Departure"), fieldtype:"Date", default:frappe.datetime.add_days(state.date,1), reqd:1 },
      { fieldname:"source", label:__("Source"), fieldtype:"Select", options:"Direct\nWalk-in\nWebsite\nOTA\nCorporate\nTravel Agent", default:"Direct" },
      { fieldname:"voucher_code", label:__("Voucher Code"), fieldtype:"Link", options:"Hotel Voucher" },
      { fieldname:"travel_agent_contract", label:__("Travel Agent Contract"), fieldtype:"Link", options:"Hotel Travel Agent Contract" },
      { fieldname:"room_requests", label:__("Room Requests"), fieldtype:"Table", reqd:1, in_place_edit:true, data:[], fields:[
        { fieldname:"room_type", label:__("Room Type"), fieldtype:"Link", options:"Hotel Room Type", reqd:1, in_list_view:1, get_query:()=>({filters:{property:state.property,enabled:1}}) },
        { fieldname:"quantity", label:__("Qty"), fieldtype:"Int", default:1, reqd:1, in_list_view:1 },
        { fieldname:"rate_plan", label:__("Rate Plan"), fieldtype:"Link", options:"Hotel Rate Plan", reqd:1, in_list_view:1, get_query:()=>({filters:{property:state.property,enabled:1}}) },
        { fieldname:"nightly_rate", label:__("Requested Nightly Rate"), fieldtype:"Currency", in_list_view:1 },
        { fieldname:"adults", label:__("Adults/Room"), fieldtype:"Int", default:2, in_list_view:1 },
        { fieldname:"children", label:__("Children/Room"), fieldtype:"Int", default:0, in_list_view:1 },
      ]},
      { fieldname:"notes", label:__("Notes"), fieldtype:"Small Text" },
    ], primary_action_label:__("Create Reservation"), primary_action: async values => {
      values.property = state.property; values.idempotency_key = `WEB-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const response = await frappe.call({ method:"hotel_pms.front_desk.quick_multi_room_booking", args:{payload:values}, freeze:true });
      dialog.hide(); frappe.set_route("Form", "Hotel Reservation", response.message.reservation);
    }}); dialog.show();
  }

  async function refreshAll() { if (!state.property) return; await Promise.all([loadToday(), loadTape()]); }
  frappe.realtime.on("hotel_room_status_changed", refreshAll);
  frappe.realtime.on("hotel_operations_update", refreshAll);
  frappe.db.get_single_value("Hotel PMS Settings", "default_property").then(value => { if (value) { propertyField.set_value(value); state.property=value; refreshAll(); } });
};
