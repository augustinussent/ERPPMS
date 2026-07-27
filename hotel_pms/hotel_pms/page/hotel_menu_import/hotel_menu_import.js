frappe.pages['hotel-menu-import'].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({ parent: wrapper, title: __('Menu & Recipe Import'), single_column: true });
  const body = $(`<div><div class="alert alert-info">CSV columns: item_code, menu_name, rate, kitchen_station, course, allergy_alert, preparation_minutes, recipe_json. recipe_json is an array such as [{"item_code":"ING-001","qty":0.2,"warehouse":"Kitchen - TBH"}]. Preview writes no Item, Stock Entry, or invoice.</div><textarea class="form-control" id="csv" rows="14" placeholder="item_code,menu_name,rate,kitchen_station,course,allergy_alert,preparation_minutes,recipe_json"></textarea><div class="mt-3"><button class="btn btn-primary" id="preview">Preview</button> <button class="btn btn-success" id="commit" disabled>Commit Valid Rows</button></div><div id="result" class="mt-3"></div></div>`).appendTo(page.body);
  let batch = null;
  page.add_field({ label: __('Outlet'), fieldtype: 'Link', options: 'Hotel Outlet', reqd: 1, change: function () { page.outlet = this.get_value(); } });
  body.find('#preview').on('click', async function () {
    if (!page.outlet) { frappe.msgprint(__('Select an outlet.')); return; }
    const csv_text = body.find('#csv').val();
    const request_key = frappe.utils.get_random(24);
    const r = await frappe.call('hotel_pms.fnb_menu_import.preview_menu_import', { outlet: page.outlet, csv_text, request_key, source_filename: 'pasted.csv' });
    batch = r.message.batch;
    body.find('#commit').prop('disabled', false);
    body.find('#result').html(`<div class="alert alert-secondary">Batch <a href="/app/hotel-menu-import-batch/${encodeURIComponent(batch)}">${frappe.utils.escape_html(batch)}</a><br>${frappe.utils.escape_html(JSON.stringify(r.message.counts || {}))}</div>`);
  });
  body.find('#commit').on('click', async function () {
    if (!batch) return;
    const r = await frappe.call('hotel_pms.fnb_menu_import.commit_menu_import', { batch });
    body.find('#result').append(`<div class="alert alert-success">${frappe.utils.escape_html(JSON.stringify(r.message))}</div>`);
  });
};
