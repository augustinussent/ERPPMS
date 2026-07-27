frappe.ui.form.on('Hotel Restaurant Order',{refresh(frm){if(frm.is_new())return;if(['Draft','Pending Confirmation'].includes(frm.doc.status))frm.add_custom_button(__('Confirm'),()=>frappe.call('hotel_pms.services.confirm_restaurant_order',{order:frm.doc.name}).then(()=>frm.reload_doc()));if(['Confirmed','In Kitchen'].includes(frm.doc.status))frm.add_custom_button(__('Send to Kitchen'),()=>frappe.call('hotel_pms.services.send_order_to_kitchen',{order:frm.doc.name,request_key:frappe.utils.get_random(12)}).then(()=>frm.reload_doc()));if(['Ready','Served','In Kitchen','Confirmed'].includes(frm.doc.status))frm.add_custom_button(__('Request Bill'),()=>frappe.call('hotel_pms.services.request_restaurant_bill',{order:frm.doc.name}).then(()=>frm.reload_doc()));if(frm.doc.status==='Bill Requested')frm.add_custom_button(__('Open POS'),()=>frappe.set_route('hotel-restaurant-pos'));if(frm.doc.status==='Bill Requested')frm.add_custom_button(__('Complete Order'),()=>frappe.call('hotel_pms.services.complete_restaurant_order',{order:frm.doc.name}).then(()=>frm.reload_doc()));}});frappe.ui.form.on('Hotel Restaurant Order',{refresh(frm){if(!frm.is_new()&&!['Billed','Cancelled'].includes(frm.doc.status))frm.add_custom_button(__('Cancel Order'),()=>frappe.prompt({fieldname:'reason',label:__('Reason'),fieldtype:'Small Text',reqd:1},v=>frappe.call('hotel_pms.services.cancel_restaurant_order',{order:frm.doc.name,reason:v.reason}).then(()=>frm.reload_doc())),__('Actions'));}});

frappe.ui.form.on('Hotel Restaurant Order',{refresh(frm){if(frm.doc.status==='Bill Requested'&&!frm.is_new()){frm.add_custom_button(__('One Bill'),()=>frappe.prompt([{fieldname:'settlement_type',label:__('Settlement Type'),fieldtype:'Select',options:'Cash\nCard\nUPI\nRoom Posting\nCity Ledger\nComplimentary',reqd:1},{fieldname:'mode_of_payment',label:__('Mode of Payment'),fieldtype:'Link',options:'Mode of Payment',depends_on:"eval:['Cash','Card','UPI'].includes(doc.settlement_type)"},{fieldname:'city_ledger_folio',label:__('City Ledger Folio'),fieldtype:'Link',options:'Hotel City Ledger Folio',depends_on:"eval:doc.settlement_type=='City Ledger'"}],v=>frappe.call('hotel_pms.services.create_default_bill_split',{order:frm.doc.name,settlement_type:v.settlement_type,mode_of_payment:v.mode_of_payment,folio:frm.doc.folio,city_ledger_folio:v.city_ledger_folio,request_key:frappe.utils.get_random(12)}).then(r=>frappe.set_route('Form','Hotel Restaurant Bill Split',r.message.splits[0]))),__('Billing'));frm.add_custom_button(__('Equal Direct Split'),()=>frappe.prompt([{fieldname:'shares',label:__('Number of Splits'),fieldtype:'Int',default:2,reqd:1},{fieldname:'settlement_type',label:__('Settlement Type'),fieldtype:'Select',options:'Cash\nCard\nUPI',reqd:1},{fieldname:'mode_of_payment',label:__('Mode of Payment'),fieldtype:'Link',options:'Mode of Payment',reqd:1}],v=>frappe.call('hotel_pms.services.create_equal_bill_splits',{order:frm.doc.name,shares:v.shares,settlement_type:v.settlement_type,mode_of_payment:v.mode_of_payment,request_key:frappe.utils.get_random(12)}).then(()=>frappe.set_route('List','Hotel Restaurant Bill Split',{restaurant_order:frm.doc.name}))),__('Billing'));}}});

frappe.ui.form.on("Hotel Restaurant Order", {
  refresh(frm) {
    if (frm.is_new()) return;
    frm.add_custom_button(__("Restaurant Control"), () => frappe.set_route("hotel-restaurant-control"), __("Control"));
    if (!["Billed", "Cancelled"].includes(frm.doc.status) && frm.doc.service_type === "Dine In") {
      frm.add_custom_button(__("Merge Tables"), () => {
        frappe.prompt({
          fieldname: "tables", label: __("Additional Tables"), fieldtype: "MultiSelectList", reqd: 1,
          get_data: txt => frappe.db.get_link_options("Hotel Restaurant Table", txt, { outlet: frm.doc.outlet, enabled: 1 }),
        }, values => frappe.call({
          method: "hotel_pms.restaurant_controls.merge_restaurant_tables",
          args: { order: frm.doc.name, tables: values.tables, request_key: frappe.utils.get_random(12) }, freeze: true,
        }).then(() => frm.reload_doc()));
      }, __("Tables"));
    }
    if (frm.doc.table_cluster) {
      frm.add_custom_button(__("Open Table Cluster"), () => frappe.set_route("Form", "Hotel Restaurant Table Cluster", frm.doc.table_cluster), __("Tables"));
    }
  },
});
