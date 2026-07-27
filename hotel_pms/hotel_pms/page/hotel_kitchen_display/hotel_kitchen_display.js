frappe.pages['hotel-kitchen-display'].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({ parent: wrapper, title: __('Kitchen Display v2'), single_column: true });
  const body = $('<div class="hotel-kds-v2"></div>').appendTo(page.body);
  let lastTicketIds = new Set();
  let soundEnabled = true;

  const esc = (value) => frappe.utils.escape_html(String(value || ''));
  const age = (seconds) => {
    const mins = Math.floor((Number(seconds) || 0) / 60);
    return mins < 60 ? `${mins}m` : `${Math.floor(mins / 60)}h ${mins % 60}m`;
  };
  const badge = (status) => {
    const cls = status === 'Ready' ? 'green' : status === 'Recalled' ? 'red' : status === 'Partially Ready' ? 'orange' : 'blue';
    return `<span class="indicator ${cls}">${esc(status)}</span>`;
  };
  function chime() {
    if (!soundEnabled) return;
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
      osc.connect(gain); gain.connect(ctx.destination); osc.start(); osc.stop(ctx.currentTime + 0.35);
    } catch (e) { /* browsers may block sound until interaction */ }
  }
  async function call(method, args) {
    const r = await frappe.call(`hotel_pms.services.${method}`, args);
    return r.message;
  }
  function renderTicket(k) {
    const lateClass = k.is_late ? 'border-danger' : k.status === 'Ready' ? 'border-success' : '';
    const context = [k.table ? `Table ${esc(k.table)}` : '', k.room ? `Room ${esc(k.room)}` : '', esc(k.guest_name)].filter(Boolean).join(' · ');
    const canPostStock = ['Restaurant Captain', 'Hotel Manager', 'System Manager'].some(role => (frappe.user_roles || []).includes(role));
    const retryStock = canPostStock && ['Queued', 'Draft Created', 'Failed', 'Cancelled'].includes(k.stock_posting_status)
      ? ` <button class="btn btn-xs btn-default stock-post" data-ticket="${esc(k.name)}">Post/Submit Stock</button>` : '';
    const stock = k.stock_posting_status && k.stock_posting_status !== 'Not Required'
      ? `<div class="small text-muted mt-2">Stock: ${esc(k.stock_posting_status)}${k.stock_entry ? ` · <a href="/app/stock-entry/${encodeURIComponent(k.stock_entry)}">${esc(k.stock_entry)}</a>` : ''}${retryStock}</div>` : '';
    const items = (k.items || []).map(i => {
      const allergy = i.allergy_alert ? `<div class="alert alert-danger py-1 px-2 mb-1"><b>ALLERGY:</b> ${esc(i.allergy_alert)}</div>` : '';
      return `<div class="border-top pt-2 mt-2 kds-item">
        ${allergy}<div class="d-flex justify-content-between"><b>${esc(i.qty)} × ${esc(i.item_name)}</b><span>${esc(i.course || '')}</span></div>
        ${i.notes ? `<div>${esc(i.notes)}</div>` : ''}
        <div class="small text-muted">${esc(i.status)} · target ${esc(i.preparation_minutes || 0)}m</div>
        <div class="mt-1">
          <button class="btn btn-xs btn-warning item-act" data-ticket="${esc(k.name)}" data-row="${esc(i.name)}" data-status="Cooking">Cook</button>
          <button class="btn btn-xs btn-success item-act" data-ticket="${esc(k.name)}" data-row="${esc(i.name)}" data-status="Ready">Ready</button>
          <button class="btn btn-xs btn-default item-act" data-ticket="${esc(k.name)}" data-row="${esc(i.name)}" data-status="Served">Serve</button>
        </div>
      </div>`;
    }).join('');
    return `<div class="col-xl-3 col-lg-4 col-md-6"><div class="card p-3 mb-3 ${lateClass}">
      <div class="d-flex justify-content-between align-items-start"><h4 class="mb-0">KOT ${esc(k.daily_kot_number)} · ${esc(k.kitchen_station)}</h4>${badge(k.status)}</div>
      <div class="small">${esc(k.restaurant_order)} · ${age(k.age_seconds)}${k.is_late ? ' · <b class="text-danger">LATE</b>' : ''}</div>
      <div>${context}</div><div class="small text-muted">Captain: ${esc(k.captain || '-')} · ${esc(k.priority || 'Normal')} · ${esc(k.course || '')}</div>
      <div class="progress mt-2" style="height:8px"><div class="progress-bar" role="progressbar" style="width:${Number(k.progress || 0)}%"></div></div>
      <div class="mt-2">
        <button class="btn btn-xs btn-primary ticket-act" data-action="accept_kitchen_ticket" data-ticket="${esc(k.name)}">Accept</button>
        <button class="btn btn-xs btn-warning ticket-act" data-action="start_kitchen_ticket" data-ticket="${esc(k.name)}">Start</button>
        <button class="btn btn-xs btn-danger recall" data-ticket="${esc(k.name)}">Recall</button>
      </div>${items}${stock}
    </div></div>`;
  }
  async function load() {
    const d = await call('get_kitchen_display', { outlet: page.outlet || null, station: page.station || null, course: page.course || null });
    const ids = new Set((d.tickets || []).map(t => t.name));
    if ([...ids].some(id => !lastTicketIds.has(id)) && lastTicketIds.size) chime();
    lastTicketIds = ids;
    body.html(`<div class="d-flex justify-content-between mb-2"><div>${__('Live KDS. Stock status is ERPNext Stock Entry state, not a parallel balance.')}</div><button class="btn btn-xs btn-default" id="sound">${soundEnabled ? 'Sound On' : 'Sound Off'}</button></div><div class="row">${(d.tickets || []).map(renderTicket).join('')}</div>`);
    body.find('#sound').on('click', function () { soundEnabled = !soundEnabled; $(this).text(soundEnabled ? 'Sound On' : 'Sound Off'); if (soundEnabled) chime(); });
    body.find('.ticket-act').on('click', async function () { await call($(this).data('action'), { ticket: $(this).data('ticket') }); load(); });
    body.find('.item-act').on('click', async function () { await call('update_kitchen_item', { ticket: $(this).data('ticket'), row_name: $(this).data('row'), status: $(this).data('status') }); load(); });
    body.find('.stock-post').on('click', async function () { await frappe.call('hotel_pms.fnb_inventory.post_ticket_recipe_consumption', { ticket: $(this).data('ticket'), submit: 1 }); load(); });
    body.find('.recall').on('click', function () {
      const ticket = $(this).data('ticket');
      frappe.prompt([{ fieldname: 'reason', label: __('Recall Reason'), fieldtype: 'Small Text', reqd: 1 }], async values => { await call('recall_kitchen_ticket', { ticket, reason: values.reason }); load(); }, __('Recall KOT'), __('Recall'));
    });
  }
  page.add_field({ label: __('Outlet'), fieldtype: 'Link', options: 'Hotel Outlet', change: function () { page.outlet = this.get_value(); load(); } });
  page.add_field({ label: __('Station'), fieldtype: 'Data', change: function () { page.station = this.get_value(); load(); } });
  page.add_field({ label: __('Course'), fieldtype: 'Select', options: '\nStarter\nMain\nDessert\nBeverage\nOther', change: function () { page.course = this.get_value(); load(); } });
  page.set_primary_action(__('Refresh'), load);
  frappe.realtime.on('hotel_kds_update', event => { if (!page.outlet || event.outlet === page.outlet) load(); });
  load();
  const timer = setInterval(load, 30000);
  $(wrapper).on('remove', () => clearInterval(timer));
};
