frappe.query_reports['Hotel Restaurant Stock Reconciliation'] = {
  filters: [
    { fieldname: 'property', label: __('Property'), fieldtype: 'Link', options: 'Hotel Property' },
    { fieldname: 'outlet', label: __('Outlet'), fieldtype: 'Link', options: 'Hotel Outlet' },
    { fieldname: 'from_date', label: __('From Date'), fieldtype: 'Date', default: frappe.datetime.add_days(frappe.datetime.get_today(), -30) },
    { fieldname: 'to_date', label: __('To Date'), fieldtype: 'Date', default: frappe.datetime.get_today() },
    { fieldname: 'stock_status', label: __('Stock Status'), fieldtype: 'Select', options: '\nQueued\nDraft Created\nSubmitted\nFailed\nCancelled\nNot Required' }
  ]
};
