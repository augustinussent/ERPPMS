frappe.pages["hotel-housekeeping-mobile"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Hotel Operations"), single_column: true });
  page.main.addClass("hotel-operations-mobile");
  const isSupervisor = frappe.user_roles.some(r => ["Housekeeping Supervisor","Hotel Manager","System Manager"].includes(r));
  const canFlagWaiting = isSupervisor || frappe.user_roles.includes("Front Desk");
  const state = { property: null, assignedOnly: frappe.user_roles.includes("Housekeeping") && !isSupervisor };

  const propertyField = page.add_field({
    label: __("Property"), fieldtype: "Link", fieldname: "property", options: "Hotel Property",
    change() { state.property = propertyField.get_value(); refreshAll(); },
  });
  page.add_inner_button(__("Refresh"), refreshAll);
  page.set_primary_action(__("Report Issue"), () => reportIssue(), "add");

  const body = $(`<div class="hom-root">
    <style>
      .hom-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0}.hom-card{border:1px solid var(--border-color);border-radius:10px;padding:12px;background:var(--card-bg)}
      .hom-card b{display:block;font-size:22px}.hom-tabs{display:flex;gap:8px;margin:12px 0;position:sticky;top:0;background:var(--bg-color);z-index:4;padding:8px 0}
      .hom-task{border:1px solid var(--border-color);border-radius:12px;padding:14px;margin:10px 0;background:var(--card-bg)}.hom-task h4{margin:0 0 4px}.hom-meta{font-size:12px;color:var(--text-muted);display:flex;flex-wrap:wrap;gap:8px}
      .hom-actions{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}.hom-actions .btn{flex:1 1 auto}.hom-priority-Critical{border-left:5px solid var(--red-500)}.hom-priority-High{border-left:5px solid var(--orange-500)}
      .hom-badge{padding:3px 7px;border-radius:999px;background:var(--subtle-fg);font-size:11px}.hom-empty{text-align:center;color:var(--text-muted);padding:30px}
      @media(max-width:700px){.layout-main-section{padding:8px!important}.hom-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.hom-actions .btn{min-height:42px}.page-head{position:sticky;top:0;z-index:5}}
    </style>
    <div class="hom-summary"></div>
    <div class="hom-tabs"><button class="btn btn-default active" data-tab="housekeeping">${__("Housekeeping")}</button><button class="btn btn-default" data-tab="engineering">${__("Engineering")}</button></div>
    <div class="hom-view hom-housekeeping"></div><div class="hom-view hom-engineering" style="display:none"></div>
  </div>`).appendTo(page.main);

  function esc(v){ return frappe.utils.escape_html(String(v == null ? "" : v)); }
  body.on("click", ".hom-tabs button", function(){ body.find(".hom-tabs button").removeClass("active"); $(this).addClass("active"); body.find(".hom-view").hide(); body.find(`.hom-${$(this).data("tab")}`).show(); });
  body.on("click", "[data-open-task]", e => frappe.set_route("Form", "Hotel Housekeeping Task", $(e.currentTarget).data("open-task")));
  body.on("click", "[data-open-ticket]", e => frappe.set_route("Form", "Hotel Maintenance Ticket", $(e.currentTarget).data("open-ticket")));

  body.on("click", "[data-hk-action]", async function(e){ e.stopPropagation(); const action=$(this).data("hk-action"), task=$(this).data("task");
    if(action==="start") return call("hotel_pms.operations.start_housekeeping_task",{task});
    if(action==="assign") return assignTask(task);
    if(action==="checklist") return checklistDialog(task);
    if(action==="waiting") return call("hotel_pms.operations.mark_guest_waiting",{task,waiting:1});
    if(action==="clear-waiting") return call("hotel_pms.operations.mark_guest_waiting",{task,waiting:0});
    if(action==="resume") return call("hotel_pms.operations.resume_housekeeping_task",{task});
    if(action==="complete") return call("hotel_pms.operations.complete_housekeeping_task",{task});
    if(action==="pause") return pauseTask(task);
    if(action==="inspect") return inspectTask(task);
    if(action==="lost") return reportLost(task);
    if(action==="issue") return reportIssue(task);
  });
  body.on("click", "[data-eng-action]", async function(e){ e.stopPropagation(); const action=$(this).data("eng-action"), ticket=$(this).data("ticket");
    if(action==="ack") return call("hotel_pms.operations.acknowledge_maintenance",{ticket});
    if(action==="start") return call("hotel_pms.operations.start_maintenance",{ticket});
    if(action==="complete") return completeMaintenance(ticket);
  });

  async function call(method,args){ await frappe.call({method,args,freeze:true}); await refreshAll(); }
  function taskButtons(t){
    const buttons=[];
    if(isSupervisor && !["Completed","Cancelled"].includes(t.status)) buttons.push(["assign",__("Assign"),"btn-default"]);
    if(!["Completed","Cancelled"].includes(t.status)) buttons.push(["checklist",__("Checklist"),"btn-default"]);
    if(canFlagWaiting && !["Completed","Cancelled"].includes(t.status)) buttons.push([t.guest_waiting?"clear-waiting":"waiting",t.guest_waiting?__("Clear Waiting"):__("Guest Waiting"),"btn-default"]);
    if(["Open","Assigned","Reclean Required"].includes(t.status)) buttons.push(["start",__("Start"),"btn-primary"]);
    if(t.status==="In Progress") buttons.push(["pause",__("Pause"),"btn-default"],["complete",__("Done"),"btn-primary"],["lost",__("Lost & Found"),"btn-default"],["issue",__("Damage"),"btn-default"]);
    if(["Paused","Waiting Engineering"].includes(t.status)) buttons.push(["resume",__("Resume"),"btn-primary"]);
    if(t.status==="Ready for Inspection" && isSupervisor) buttons.push(["inspect",__("Inspect"),"btn-primary"]);
    return buttons.map(b=>`<button class="btn ${b[2]}" data-hk-action="${b[0]}" data-task="${esc(t.name)}">${b[1]}</button>`).join("");
  }
  function renderHK(data){
    const m=data.metrics||{}; body.find(".hom-summary").html([[__("Open"),m.open||0],[__("In progress"),m.in_progress||0],[__("Inspection"),m.inspection||0],[__("Reclean"),m.reclean||0],[__("Paused"),m.paused||0],[__("Assigned"),m.assigned||0]].map(x=>`<div class="hom-card"><span>${x[0]}</span><b>${x[1]}</b></div>`).join(""));
    const html=(data.tasks||[]).map(t=>`<div class="hom-task hom-priority-${esc(t.priority)}" data-open-task="${esc(t.name)}"><h4>${esc(t.room_number||t.room)} · ${esc(t.task_type)}</h4><div class="hom-meta"><span class="hom-badge">${esc(t.status)}</span><span>${esc(t.priority)}</span><span>${esc(t.assigned_to||__("Unassigned"))}</span>${t.next_arrival_at?`<span>${__("Next arrival")}: ${esc(frappe.datetime.str_to_user(t.next_arrival_at))}</span>`:""}${t.started_at?`<span>${__("Started")}: ${esc(frappe.datetime.str_to_user(t.started_at))}</span>`:""}</div><div class="hom-actions">${taskButtons(t)}</div></div>`).join("");
    body.find(".hom-housekeeping").html(html||`<div class="hom-empty">${__("No active housekeeping tasks")}</div>`);
  }
  function renderEngineering(data){
    const html=(data.tickets||[]).map(t=>`<div class="hom-task ${String(t.priority).startsWith("Critical")?"hom-priority-Critical":""}" data-open-ticket="${esc(t.name)}"><h4>${esc(t.room||t.location||"-")} · ${esc(t.subject)}</h4><div class="hom-meta"><span class="hom-badge">${esc(t.status)}</span><span>${esc(t.priority)}</span><span>${esc(t.sla_status)}</span><span>${esc(t.assigned_to||__("Unassigned"))}</span></div><div class="hom-actions">${["Open","Assigned"].includes(t.status)?`<button class="btn btn-default" data-eng-action="ack" data-ticket="${esc(t.name)}">${__("Acknowledge")}</button>`:""}${["Open","Acknowledged","Assigned","Paused","Waiting Vendor","Waiting Parts"].includes(t.status)?`<button class="btn btn-primary" data-eng-action="start" data-ticket="${esc(t.name)}">${__("Start")}</button>`:""}${t.status==="In Progress"?`<button class="btn btn-primary" data-eng-action="complete" data-ticket="${esc(t.name)}">${__("Repair Done")}</button>`:""}</div></div>`).join("");
    body.find(".hom-engineering").html(html||`<div class="hom-empty">${__("No active engineering tickets")}</div>`);
  }
  async function refreshAll(){ if(!state.property) return; const [hk,eng]=await Promise.all([frappe.call({method:"hotel_pms.operations.get_housekeeping_queue",args:{property:state.property,assigned_only:state.assignedOnly?1:0}}),frappe.call({method:"hotel_pms.operations.get_engineering_queue",args:{property:state.property}})]); renderHK(hk.message); renderEngineering(eng.message); }

  function assignTask(task){ const d=new frappe.ui.Dialog({title:__("Assign Housekeeper"),fields:[{fieldname:"assigned_to",label:__("Housekeeper"),fieldtype:"Link",options:"User",reqd:1}],primary_action_label:__("Assign"),primary_action:async v=>{d.hide();await call("hotel_pms.operations.assign_housekeeping_task",{task,assigned_to:v.assigned_to,idempotency_key:`WEB-${Date.now()}`});}});d.show(); }
  async function checklistDialog(task){
    const response=await frappe.call({method:"hotel_pms.operations.get_housekeeping_task",args:{task}}),doc=response.message||{};
    const data=(doc.checklist_items||[]).map(r=>({row_name:r.name,area:r.area,item_label:r.item_label,result:r.result,notes:r.notes}));
    const d=new frappe.ui.Dialog({title:__("Cleaning Checklist - {0}",[doc.room||task]),size:"extra-large",fields:[{fieldname:"checklist",label:__("Checklist"),fieldtype:"Table",in_place_edit:true,data,fields:[{fieldname:"row_name",fieldtype:"Data",hidden:1},{fieldname:"area",label:__("Area"),fieldtype:"Data",read_only:1,in_list_view:1},{fieldname:"item_label",label:__("Item"),fieldtype:"Data",read_only:1,in_list_view:1},{fieldname:"result",label:__("Result"),fieldtype:"Select",options:`Pending\nOK\nNot OK\nNot Applicable\nReported to Engineering`,in_list_view:1,reqd:1},{fieldname:"notes",label:__("Notes"),fieldtype:"Small Text",in_list_view:1}]}],primary_action_label:__("Save Checklist"),primary_action:async v=>{const rows=v.checklist||[];for(const r of rows){await frappe.call({method:"hotel_pms.operations.update_housekeeping_checklist",args:{task,row_name:r.row_name,result:r.result,notes:r.notes}});}d.hide();await refreshAll();}});d.show();
  }
  function pauseTask(task){ const d=new frappe.ui.Dialog({title:__("Pause Cleaning"),fields:[{fieldname:"reason",label:__("Reason"),fieldtype:"Small Text",reqd:1},{fieldname:"waiting_engineering",label:__("Waiting Engineering"),fieldtype:"Check"}],primary_action_label:__("Pause"),primary_action:async v=>{d.hide();await call("hotel_pms.operations.pause_housekeeping_task",{task,...v});}});d.show(); }
  function inspectTask(task){ const d=new frappe.ui.Dialog({title:__("Supervisor Inspection"),fields:[{fieldname:"decision",label:__("Decision"),fieldtype:"Select",options:"Pass\nReclean Required",default:"Pass",reqd:1},{fieldname:"notes",label:__("Notes"),fieldtype:"Small Text"}],primary_action_label:__("Save Inspection"),primary_action:async v=>{d.hide();await call("hotel_pms.operations.inspect_housekeeping_task",{task,idempotency_key:`WEB-${Date.now()}`,...v});}});d.show(); }
  function reportLost(task){ const d=new frappe.ui.Dialog({title:__("Report Lost & Found"),fields:[{fieldname:"item_category",label:__("Category"),fieldtype:"Select",options:"Cash\nDocument / ID\nJewelry\nElectronics\nClothing\nMedicine\nBag / Luggage\nKey / Card\nOther",default:"Other",reqd:1},{fieldname:"item_description",label:__("Description"),fieldtype:"Small Text",reqd:1},{fieldname:"found_location",label:__("Exact Location"),fieldtype:"Data"},{fieldname:"sensitive_item",label:__("Sensitive / High Value"),fieldtype:"Check"},{fieldname:"storage_location",label:__("Temporary Storage"),fieldtype:"Data"}],primary_action_label:__("Report"),primary_action:async v=>{d.hide();await call("hotel_pms.operations.report_lost_and_found",{task,data:v,idempotency_key:`WEB-${Date.now()}`});}});d.show(); }
  function reportIssue(task){ const d=new frappe.ui.Dialog({title:__("Report Engineering Issue"),fields:[{fieldname:"room",label:__("Room"),fieldtype:"Link",options:"Hotel Room",default:null},{fieldname:"subject",label:__("Subject"),fieldtype:"Data",reqd:1},{fieldname:"problem_category",label:__("Category"),fieldtype:"Select",options:"Electrical\nPlumbing\nHVAC / AC\nWater Heater\nFurniture / Fixture\nBuilding / Leakage\nNetwork / Wi-Fi\nAppliance\nLift\nSafety\nOther",default:"Other"},{fieldname:"description",label:__("Description"),fieldtype:"Text",reqd:1},{fieldname:"priority",label:__("Priority"),fieldtype:"Select",options:"Critical - Guest Complaint\nCritical - Safety / Spreading Damage\nHigh - Guest Visible\nMedium\nLow",default:"Medium"},{fieldname:"guest_impact",label:__("Guest Impact"),fieldtype:"Select",options:"None\nMinor Inconvenience\nMajor Inconvenience\nGuest Cannot Use Facility\nRoom Move Required",default:"None"},{fieldname:"affects_room_sale",label:__("Block Room From Sale"),fieldtype:"Check"}],primary_action_label:__("Create Ticket"),primary_action:async v=>{if(task){const x=await frappe.call({method:"hotel_pms.operations.get_housekeeping_task",args:{task}});v.room=x.message.room;v.reservation=x.message.reservation;v.housekeeping_task=task;v.property=x.message.property;v.source="Housekeeping";}else{v.property=state.property;v.source="Front Office";}d.hide();await call("hotel_pms.operations.report_maintenance_issue",{data:v,idempotency_key:`WEB-${Date.now()}`});}});d.show(); }
  function completeMaintenance(ticket){ const d=new frappe.ui.Dialog({title:__("Complete Repair"),fields:[{fieldname:"root_cause",label:__("Root Cause"),fieldtype:"Small Text",reqd:1},{fieldname:"corrective_action",label:__("Corrective Action"),fieldtype:"Text",reqd:1},{fieldname:"materials_used",label:__("Materials / Parts"),fieldtype:"Small Text"},{fieldname:"prevention_notes",label:__("Prevention / HIKMAH"),fieldtype:"Text"},{fieldname:"post_maintenance_cleaning_required",label:__("Post-maintenance Cleaning Required"),fieldtype:"Check"},{fieldname:"cleaning_instructions",label:__("Practical Cleaning Instructions"),fieldtype:"Text",depends_on:"post_maintenance_cleaning_required"}],primary_action_label:__("Complete Repair"),primary_action:async v=>{d.hide();await call("hotel_pms.operations.complete_maintenance",{ticket,data:v,idempotency_key:`WEB-${Date.now()}`});}});d.show(); }

  frappe.realtime.on("hotel_operations_update", data=>{ refreshAll(); if(window.Notification && Notification.permission==="granted" && data.subject) new Notification(data.subject,{body:data.message||""}); });
  frappe.realtime.on("hotel_room_status_changed", refreshAll);
  if(window.Notification && Notification.permission==="default") Notification.requestPermission();
  frappe.db.get_single_value("Hotel PMS Settings","default_property").then(v=>{if(v){propertyField.set_value(v);state.property=v;refreshAll();}});
};
