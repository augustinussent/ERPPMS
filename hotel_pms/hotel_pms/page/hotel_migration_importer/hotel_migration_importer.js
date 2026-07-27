frappe.pages["hotel-migration-importer"].on_page_load=function(wrapper){
 const page=frappe.ui.make_app_page({parent:wrapper,title:__("Hotel Migration Importer"),single_column:true});
 const batch=page.add_field({label:__("Batch"),fieldtype:'Link',fieldname:'batch',options:'Hotel Migration Batch',change:load});
 page.add_inner_button(__("Dry Run"),()=>run('dry_run_batch')); page.add_inner_button(__("Commit Import"),()=>run('commit_batch')); page.add_inner_button(__("Rollback Safe Rows"),()=>run('rollback_batch'));
 const body=$(`<div><div class="alert alert-warning">${__("Dry run first. Accounting deposits are review-only and are never silently posted.")}</div><pre></pre></div>`).appendTo(page.main);
 async function load(){if(!batch.get_value())return;const r=await frappe.call({method:'hotel_pms.migration.get_batch_summary',args:{batch:batch.get_value()}});body.find('pre').text(JSON.stringify(r.message,null,2))}
 async function run(method){if(!batch.get_value())return frappe.msgprint(__("Select a batch."));const r=await frappe.call({method:`hotel_pms.migration.${method}`,args:{batch:batch.get_value()},freeze:true});body.find('pre').text(JSON.stringify(r.message,null,2))}
};
