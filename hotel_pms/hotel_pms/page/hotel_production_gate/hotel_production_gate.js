frappe.pages["hotel-production-gate"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __("Hotel Production Gate"),
    single_column: true,
  });
  const run = page.add_field({
    label: __("Gate Run"),
    fieldtype: "Link",
    fieldname: "run",
    options: "Hotel Production Gate Run",
    change: load,
  });
  const body = $(
    `<div>
      <style>
        .pg-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
        .pg-card{border:1px solid var(--border-color);padding:12px;border-radius:8px}
        .pg-table{width:100%;margin-top:14px}
        .pg-table th,.pg-table td{border-bottom:1px solid var(--border-color);padding:7px;text-align:left;vertical-align:top}
        .pg-bad{color:var(--red-500)}.pg-good{color:var(--green-500)}.pg-warn{color:var(--orange-500)}
        .pg-pre{white-space:pre-wrap;max-width:520px;font-size:11px}
      </style>
      <div class="pg-grid"></div><div class="pg-content"></div>
    </div>`
  ).appendTo(page.main);
  const e = (x) => frappe.utils.escape_html(String(x ?? ""));
  const canManage = frappe.user_roles.includes("System Manager") || frappe.user_roles.includes("Hotel Manager");
  const isSystem = frappe.user_roles.includes("System Manager");

  if (isSystem) {
    page.add_inner_button(__("Create Manifest"), () => {
      frappe.prompt([
        {fieldname:"promotion_target_version",label:__("Promotion Target"),fieldtype:"Data",default:"1.0.0",reqd:1},
        {fieldname:"frappe_version",label:__("Pinned Frappe Version"),fieldtype:"Data"},
        {fieldname:"erpnext_version",label:__("Pinned ERPNext Version"),fieldtype:"Data"},
        {fieldname:"image_digest",label:__("Pinned Image Digest"),fieldtype:"Data",reqd:1},
        {fieldname:"artifact_sha256",label:__("Package SHA-256"),fieldtype:"Data"},
        {fieldname:"package_url",label:__("Package URL"),fieldtype:"Data"},
        {fieldname:"git_commit",label:__("Git Commit"),fieldtype:"Data"},
        {fieldname:"notes",label:__("Notes"),fieldtype:"Small Text"},
      ], async (v) => {
        const r = await frappe.call({method:"hotel_pms.production_validation.create_release_manifest",args:v,freeze:true});
        frappe.set_route("Form", "Hotel Release Manifest", r.message.name);
      }, __("Create Frozen-Source Manifest"));
    });
    page.add_inner_button(__("Freeze Manifest"), () => {
      frappe.prompt([{fieldname:"manifest_name",label:__("Manifest"),fieldtype:"Link",options:"Hotel Release Manifest",reqd:1}],
        async (v) => {
          const r = await frappe.call({method:"hotel_pms.production_validation.freeze_release_manifest",args:v,freeze:true});
          frappe.show_alert({message:__("Manifest frozen: {0}",[r.message.name]),indicator:"green"});
        }, __("Freeze Release Manifest"));
    });
  }

  if (canManage) {
    page.add_inner_button(__("Create Gate Run"), () => {
      frappe.prompt([
        {fieldname:"property",label:__("Property"),fieldtype:"Link",options:"Hotel Property"},
        {fieldname:"environment_name",label:__("Environment"),fieldtype:"Select",options:"Staging\nPre-production\nProduction",default:"Staging",reqd:1},
        {fieldname:"release_manifest",label:__("Frozen Manifest"),fieldtype:"Link",options:"Hotel Release Manifest",reqd:1},
        {fieldname:"reconciliation_from_date",label:__("Reconciliation From"),fieldtype:"Date"},
        {fieldname:"reconciliation_to_date",label:__("Reconciliation To"),fieldtype:"Date"},
      ], async (v) => {
        const r = await frappe.call({method:"hotel_pms.production_gate.create_gate_run",args:v,freeze:true});
        await run.set_value(r.message.name);
      }, __("Create Production Gate"));
    });

    page.add_inner_button(__("Record Rehearsal"), () => {
      frappe.prompt([
        {fieldname:"property",label:__("Property"),fieldtype:"Link",options:"Hotel Property"},
        {fieldname:"run_type",label:__("Type"),fieldtype:"Select",options:"Blank Install\nUpgrade\nRestore\nRollback\nConcurrency\nPerformance\nSecurity\nSmoke",reqd:1},
        {fieldname:"environment_name",label:__("Environment"),fieldtype:"Select",options:"Staging\nPre-production\nProduction",default:"Staging",reqd:1},
        {fieldname:"status",label:__("Status"),fieldtype:"Select",options:"Passed\nFailed",reqd:1},
        {fieldname:"started_at",label:__("Started At"),fieldtype:"Datetime",reqd:1},
        {fieldname:"completed_at",label:__("Completed At"),fieldtype:"Datetime",reqd:1},
        {fieldname:"source_version",label:__("Source Version"),fieldtype:"Data"},
        {fieldname:"measured_rto_minutes",label:__("Measured RTO Minutes"),fieldtype:"Float"},
        {fieldname:"result_summary",label:__("Result Summary"),fieldtype:"Long Text"},
        {fieldname:"command",label:__("Command Used"),fieldtype:"Small Text"},
        {fieldname:"evidence_file",label:__("Evidence File"),fieldtype:"Attach"},
        {fieldname:"evidence_url",label:__("Evidence URL"),fieldtype:"Data"},
      ], async (v) => {
        const r = await frappe.call({method:"hotel_pms.production_validation.record_rehearsal",args:v,freeze:true});
        frappe.show_alert({message:__("Rehearsal recorded: {0}",[r.message.name]),indicator:r.message.status === "Passed" ? "green" : "red"});
        load();
      }, __("Immutable Rehearsal Evidence"));
    });

    page.add_inner_button(__("Import Parallel Run"), () => {
      frappe.prompt([
        {fieldname:"property",label:__("Property"),fieldtype:"Link",options:"Hotel Property",reqd:1},
        {fieldname:"source_system",label:__("Comparison System"),fieldtype:"Data",reqd:1},
        {fieldname:"from_date",label:__("From Date"),fieldtype:"Date",reqd:1},
        {fieldname:"to_date",label:__("To Date"),fieldtype:"Date",reqd:1},
        {fieldname:"source_file",label:__("CSV Evidence"),fieldtype:"Attach",reqd:1},
        {fieldname:"default_tolerance",label:__("Default Tolerance"),fieldtype:"Float",default:0},
        {fieldname:"notes",label:__("Notes"),fieldtype:"Small Text"},
      ], async (v) => {
        const r = await frappe.call({method:"hotel_pms.production_validation.create_parallel_run_batch_from_csv",args:v,freeze:true});
        frappe.show_alert({message:__("Parallel batch: {0} ({1})",[r.message.name,r.message.status]),indicator:r.message.status === "Passed" ? "green" : "orange"});
        load();
      }, __("Parallel-run Reconciliation"));
    });

    page.add_inner_button(__("Capture Preflight"), async () => {
      if (!run.get_value()) return frappe.msgprint(__("Select a gate run."));
      const r = await frappe.call({method:"hotel_pms.staging_execution.capture_staging_preflight",args:{gate_run:run.get_value()},freeze:true});
      frappe.show_alert({message:__("Preflight: {0}",[r.message.result.summary.status]),indicator:r.message.result.summary.status === "Passed" ? "green" : "red"});
      load();
    });

    page.add_inner_button(__("Run Smoke Suite"), async () => {
      if (!run.get_value()) return frappe.msgprint(__("Select a gate run."));
      const r = await frappe.call({method:"hotel_pms.staging_execution.run_smoke_suite",args:{gate_run:run.get_value()},freeze:true});
      frappe.show_alert({message:__("Smoke suite: {0}",[r.message.summary.status]),indicator:r.message.summary.status === "Passed" ? "green" : "red"});
      load();
    });

    page.add_inner_button(__("Capture Reconciliation"), async () => {
      if (!run.get_value()) return frappe.msgprint(__("Select a gate run."));
      const r = await frappe.call({method:"hotel_pms.staging_execution.capture_reconciliation_snapshot",args:{gate_run:run.get_value()},freeze:true});
      frappe.show_alert({message:__("Reconciliation snapshot: {0}",[r.message.result.status]),indicator:r.message.result.status === "Passed" ? "green" : "red"});
      load();
    });

    page.add_inner_button(__("Build Cutover Bundle"), async () => {
      if (!run.get_value()) return frappe.msgprint(__("Select a gate run."));
      const r = await frappe.call({method:"hotel_pms.staging_execution.build_cutover_bundle",args:{gate_run:run.get_value()},freeze:true});
      frappe.show_alert({message:__("Cutover bundle created: {0}",[r.message.file_url]),indicator:"green"});
      load();
    });

    page.add_inner_button(__("Run Automated Checks"), async () => {
      if (!run.get_value()) return frappe.msgprint(__("Select a gate run."));
      await frappe.call({method:"hotel_pms.production_gate.execute_automated_checks",args:{run_name:run.get_value()},freeze:true});
      load();
    });

    page.add_inner_button(__("Record Manual Evidence"), () => {
      if (!run.get_value()) return frappe.msgprint(__("Select a gate run."));
      frappe.prompt([
        {fieldname:"check_code",label:__("Check Code"),fieldtype:"Data",reqd:1},
        {fieldname:"status",label:__("Status"),fieldtype:"Select",options:"Passed\nWarning\nFailed\nNot Applicable",reqd:1},
        {fieldname:"measured_value",label:__("Measured Value"),fieldtype:"Data"},
        {fieldname:"evidence_url",label:__("Evidence URL"),fieldtype:"Data"},
        {fieldname:"details",label:__("Details"),fieldtype:"Long Text"},
      ], async (v) => {
        await frappe.call({method:"hotel_pms.production_gate.record_manual_check",args:{run_name:run.get_value(),...v},freeze:true});
        load();
      }, __("Manual Gate Evidence"));
    });
  }

  page.add_inner_button(__("Department Sign-off"), () => {
    if (!run.get_value()) return frappe.msgprint(__("Select a gate run."));
    frappe.prompt([
      {fieldname:"department",label:__("Department"),fieldtype:"Select",options:"Front Office\nHousekeeping\nEngineering\nSales & Banquet\nF&B\nFinance\nIT\nManagement",reqd:1},
      {fieldname:"status",label:__("Status"),fieldtype:"Select",options:"Approved\nRejected",reqd:1},
      {fieldname:"comments",label:__("Comments"),fieldtype:"Small Text"},
    ], async (v) => {
      await frappe.call({method:"hotel_pms.production_gate.submit_signoff",args:{run_name:run.get_value(),...v},freeze:true});
      load();
    }, __("Department Sign-off"));
  });

  if (isSystem) {
    page.add_inner_button(__("Final Decision"), () => {
      if (!run.get_value()) return frappe.msgprint(__("Select a gate run."));
      frappe.prompt([
        {fieldname:"decision",label:__("Decision"),fieldtype:"Select",options:"Go\nNo-Go\nRollback",reqd:1},
        {fieldname:"notes",label:__("Decision Notes"),fieldtype:"Long Text",reqd:1},
      ], async (v) => {
        await frappe.call({method:"hotel_pms.production_gate.decide_go_live",args:{run_name:run.get_value(),...v},freeze:true});
        load();
      }, __("Final Go-live Decision"));
    });
    page.add_inner_button(__("Prepare Promotion"), () => {
      if (!run.get_value()) return frappe.msgprint(__("Select a gate run."));
      frappe.prompt([
        {fieldname:"manifest_name",label:__("Frozen Manifest"),fieldtype:"Link",options:"Hotel Release Manifest",reqd:1},
        {fieldname:"promoted_artifact_sha256",label:__("Final Package SHA-256"),fieldtype:"Data",reqd:1},
        {fieldname:"promoted_image_digest",label:__("Final Image Digest"),fieldtype:"Data",reqd:1},
        {fieldname:"promoted_package_url",label:__("Final Package URL"),fieldtype:"Data"},
        {fieldname:"notes",label:__("Promotion Notes"),fieldtype:"Long Text",reqd:1},
      ], async (v) => {
        const r = await frappe.call({method:"hotel_pms.production_validation.prepare_release_promotion",args:{run_name:run.get_value(),...v},freeze:true});
        frappe.show_alert({message:__("Promotion prepared for {0}; deploy and verify the final artifact.",[r.message.manifest.promotion_target_version]),indicator:"green"});
        load();
      }, __("Prepare Controlled Promotion"));
    });
  }

  async function load() {
    const gateResult = await frappe.call({method:"hotel_pms.production_gate.get_gate_dashboard",args:{run_name:run.get_value() || null}});
    const d = gateResult.message;
    if (!run.get_value()) {
      body.find(".pg-grid").empty();
      body.find(".pg-content").html(`<h4>${__("Recent Runs")}</h4><table class="pg-table"><tr><th>Run</th><th>Property</th><th>Release</th><th>Status</th><th>Decision</th><th>Promotion</th></tr>${(d.runs || []).map(x => `<tr><td><a href="#" data-run="${e(x.name)}">${e(x.name)}</a></td><td>${e(x.property || "All")}</td><td>${e(x.release_version)}</td><td>${e(x.status)}</td><td>${e(x.go_live_decision)}</td><td>${e(x.promotion_status)}</td></tr>`).join("")}</table>`);
      body.find("[data-run]").on("click", function (ev) { ev.preventDefault(); run.set_value($(this).data("run")); });
      return;
    }
    const validationResult = await frappe.call({method:"hotel_pms.production_validation.get_validation_dashboard",args:{run_name:run.get_value()}});
    const v = validationResult.message || {};
    body.find(".pg-grid").html(`
      <div class="pg-card"><small>Status</small><h3>${e(d.status)}</h3></div>
      <div class="pg-card"><small>Blockers</small><h3 class="pg-bad">${e(d.blocker_count)}</h3></div>
      <div class="pg-card"><small>Warnings</small><h3 class="pg-warn">${e(d.warning_count)}</h3></div>
      <div class="pg-card"><small>Decision</small><h3>${e(d.go_live_decision)}</h3></div>
      <div class="pg-card"><small>Promotion</small><h3>${e(d.promotion_status)}</h3></div>
      <div class="pg-card"><small>Manifest</small><h3>${e(d.release_manifest)}</h3></div>`);
    const rehearsalRows = Object.entries(v.rehearsals || {}).map(([type, item]) => {
      const record = item.record || {};
      return `<tr><td>${e(type)}</td><td class="${item.passed ? "pg-good" : "pg-bad"}">${item.passed ? "Passed" : "Missing / Mismatch"}</td><td>${e(record.name)}</td><td>${e(record.completed_at)}</td></tr>`;
    }).join("");
    body.find(".pg-content").html(`
      <h4>${__("Checks")}</h4>
      <table class="pg-table"><tr><th>Category</th><th>Check</th><th>Status</th><th>Measured</th><th>Threshold</th><th>Details</th></tr>${(d.checks || []).map(x => `<tr><td>${e(x.category)}</td><td>${e(x.title)}</td><td class="${x.status === "Failed" ? "pg-bad" : x.status === "Passed" ? "pg-good" : x.status === "Warning" ? "pg-warn" : ""}">${e(x.status)}</td><td>${e(x.measured_value)}</td><td>${e(x.threshold)}</td><td class="pg-pre">${e(x.details)}</td></tr>`).join("")}</table>
      <h4>${__("Immutable Rehearsals")}</h4>
      <table class="pg-table"><tr><th>Type</th><th>Match</th><th>Record</th><th>Completed</th></tr>${rehearsalRows}</table>
      <h4>${__("Parallel Run")}</h4><div class="pg-card"><b>${e(v.parallel_status)}</b><div class="pg-pre">${e(JSON.stringify(v.parallel || {}, null, 2))}</div></div>
      <h4>${__("Sign-offs")}</h4>
      <table class="pg-table"><tr><th>Department</th><th>Status</th><th>Approver</th><th>Signed</th></tr>${(d.signoffs || []).map(x => `<tr><td>${e(x.department)}</td><td>${e(x.status)}</td><td>${e(x.approver)}</td><td>${e(x.signed_at)}</td></tr>`).join("")}</table>`);
  }
  load();
};
