frappe.pages["hotel-platform-console"].on_page_load = function(wrapper) {
 const page=frappe.ui.make_app_page({parent:wrapper,title:__("Hotel Platform Console"),single_column:true});
 const property=page.add_field({label:__("Property"),fieldtype:"Link",fieldname:"property",options:"Hotel Property"});
 page.add_inner_button(__("Refresh"),load); page.add_inner_button(__("Verify Latest Backup"),verifyBackup);
 page.add_inner_button(__("Process Webhooks"),async()=>{await frappe.call({method:"hotel_pms.webhooks.process_webhook_queue",freeze:true});load();});
 const body=$(`<div><style>.hpc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.hpc-card{padding:14px;border:1px solid var(--border-color);border-radius:8px}.hpc-card b{display:block;font-size:22px}.hpc-table{width:100%;margin-top:18px}.hpc-table td,.hpc-table th{padding:7px;border-bottom:1px solid var(--border-color)}</style><div class="hpc-grid"></div><div class="hpc-details"></div></div>`).appendTo(page.main);
 const e=x=>frappe.utils.escape_html(String(x??""));
 async function load(){const r=await frappe.call({method:"hotel_pms.platform.get_platform_dashboard",args:{property:property.get_value()}});const d=r.message; body.find('.hpc-grid').html(Object.entries(d.cards).map(([k,v])=>`<div class="hpc-card"><span>${e(k)}</span><b>${e(v)}</b></div>`).join('')); body.find('.hpc-details').html(`<h4>${__("Storage")}</h4><pre>${e(JSON.stringify(d.storage,null,2))}</pre><h4>${__("Access Review")}</h4><pre>${e(JSON.stringify(d.access_review,null,2))}</pre><h4>${__("Recent Health")}</h4><pre>${e(JSON.stringify(d.health,null,2))}</pre><h4>${__("Property Metrics")}</h4><pre>${e(JSON.stringify(d.metrics_by_property,null,2))}</pre><h4>${__("Dead-letter Webhooks")}</h4><pre>${e(JSON.stringify(d.dead_webhooks,null,2))}</pre>`);}
 async function verifyBackup(){await frappe.call({method:"hotel_pms.platform.verify_latest_backup",freeze:true});load();}
 load();
};
