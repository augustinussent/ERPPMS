frappe.provide('hotel_pms');
frappe.ready(async function(){
 if(!frappe.boot || !frappe.boot.hotel_pms_property_scope) return;
 const scope=frappe.boot.hotel_pms_property_scope, props=scope.properties||[];
 hotel_pms.current_property=scope.current_property;
 if(!props.length || !frappe.ui?.toolbar) return;
 const label=()=>hotel_pms.current_property||__('Select Property');
 const button=$(`<button class="btn-reset nav-link dropdown-toggle" title="${__('Hotel Property')}"><span class="ellipsis">${frappe.utils.escape_html(label())}</span></button>`);
 const menu=$('<div class="dropdown-menu dropdown-menu-right"></div>');
 props.forEach(p=>$(`<a class="dropdown-item" href="#">${frappe.utils.escape_html(p)}</a>`).on('click',async e=>{e.preventDefault();await frappe.call({method:'hotel_pms.platform.set_current_property',args:{property_name:p}});hotel_pms.current_property=p;location.reload();}).appendTo(menu));
 const wrap=$('<div class="dropdown"></div>').append(button,menu); button.on('click',()=>menu.toggleClass('show'));
 $('.navbar .navbar-nav').last().prepend(wrap);
});
