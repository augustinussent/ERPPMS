from __future__ import annotations
import json, os
from datetime import datetime
import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, getdate, now_datetime, nowdate
from hotel_pms import __version__
from hotel_pms.platform import assigned_properties, is_privileged
from hotel_pms.production_gate_rules import gate_status, money_variance, summarize_checks, threshold_status
from hotel_pms.production_validation import create_validation_evidence, validation_gate_results

REQUIRED_SIGNOFFS=("Front Office","Housekeeping","Engineering","Sales & Banquet","F&B","Finance","IT","Management")
SIGNOFF_ROLES={
 "Front Office":{"Front Desk","Night Auditor","Hotel Manager"},
 "Housekeeping":{"Housekeeping Supervisor","Hotel Manager"},
 "Engineering":{"Engineering Supervisor","Hotel Manager"},
 "Sales & Banquet":{"Hotel Sales","Banquet","Hotel Manager"},
 "F&B":{"Restaurant Captain","Restaurant Cashier","Hotel Manager"},
 "Finance":{"Accounts Manager","Credit Manager","Hotel Manager"},
 "IT":{"System Manager"},
 "Management":{"Hotel Manager","System Manager"},
}
CHECKS=(
 ("Platform","APP_VERSION","Release version and installed applications","Automated",1),
 ("Platform","STAGING_PREFLIGHT","Staging environment preflight captured for exact artifact","Automated",1),
 ("Platform","SMOKE_REHEARSAL","Read-only smoke rehearsal matches frozen release","Automated",1),
 ("Platform","MANIFEST_INTEGRITY","Frozen release manifest matches installed source and image","Automated",1),
 ("Platform","BLANK_INSTALL_REHEARSAL","Blank-install rehearsal matches frozen release","Automated",1),
 ("Platform","UPGRADE_REHEARSAL","Upgrade rehearsal matches frozen release","Automated",1),
 ("Platform","DATABASE","Database connectivity","Automated",1),
 ("Platform","SCHEDULER","Worker and scheduler heartbeat","Automated",1),
 ("Platform","BACKUP_FRESHNESS","Recent backup exists","Automated",1),
 ("Platform","BACKUP_CHECKSUM","Latest backup checksum verified","Automated",1),
 ("Platform","SYNC_QUEUE","ERPNext synchronization queue clean","Automated",1),
 ("Platform","WEBHOOK_DLQ","Webhook dead-letter queue clean","Automated",1),
 ("Platform","PROPERTY_ACCESS","Property access assignments complete","Automated",1),
 ("Accounting","ACCOUNTING_RECON","Folio and ERPNext invoice reconciliation","Automated",1),
 ("Accounting","RECON_SNAPSHOT","Immutable accounting, stock and sync-key snapshot","Automated",1),
 ("Accounting","CASHIER_RECON","Cashier shifts reconciled","Automated",1),
 ("Accounting","ACCOUNTANT_REVIEW","Tax, service charge, and chart mapping reviewed","Manual",1),
 ("Inventory & Operations","STOCK_RECON","Restaurant invoice and stock-ledger reconciliation","Automated",1),
 ("Inventory & Operations","CONCURRENCY_REHEARSAL","Concurrency rehearsal matches frozen release","Automated",1),
 ("Inventory & Operations","OPERATIONS_UAT","End-to-end departmental operation tests","Manual",1),
 ("Security","PUBLIC_SECURITY","Public feature security prerequisites","Automated",1),
 ("Security","SECURITY_REHEARSAL","Security rehearsal matches frozen release","Automated",1),
 ("Security","PEN_TEST","Property isolation and application penetration test","Manual",1),
 ("Security","DEPENDENCY_SCAN","Dependency and container vulnerability scan","Manual",1),
 ("Security","SECRET_ROTATION","Secret rotation drill","Manual",1),
 ("Reliability & DR","RESTORE_REHEARSAL","Restore rehearsal matches frozen release","Automated",1),
 ("Reliability & DR","ROLLBACK_REHEARSAL","Rollback rehearsal matches frozen release","Automated",1),
 ("Reliability & DR","RESTORE_DRILL","Isolated database and file restore drill","Manual",1),
 ("Reliability & DR","DR_DRILL","Disaster recovery and failover drill","Manual",1),
 ("Reliability & DR","ROLLBACK_DRILL","Release rollback drill","Manual",1),
 ("Performance","PERFORMANCE_REHEARSAL","Performance rehearsal matches frozen release","Automated",1),
 ("Performance","LOAD_TEST","Peak booking, checkout, and POS load test","Manual",1),
 ("Performance","SLOW_QUERY_REVIEW","Slow query and index review","Manual",1),
 ("Operational Readiness","PARALLEL_RECON","Parallel-run batch reconciles without warning or failure","Automated",1),
 ("Operational Readiness","CUTOVER_BUNDLE","Private cutover evidence bundle generated for exact artifact","Automated",1),
 ("Operational Readiness","PARALLEL_RUN","Parallel run reviewed and accepted by departments","Manual",1),
 ("Operational Readiness","TRAINING","Department training completed","Manual",1),
 ("Operational Readiness","SOP_ESCALATION","SOP, support roster, and escalation approved","Manual",1),
 ("Operational Readiness","GO_LIVE_PLAN","Freeze, cutover, rollback, and decision points approved","Manual",1),
)

def _require_manager():
    if not is_privileged() and "Hotel Manager" not in frappe.get_roles():
        frappe.throw(_("Hotel Manager or System Manager role required."), frappe.PermissionError)

def _validate_property(property_name):
    if property_name and property_name not in assigned_properties():
        frappe.throw(_("Not permitted for this property."), frappe.PermissionError)

def _ensure_gate_open(doc):
    if (doc.go_live_decision or "Pending") != "Pending":
        frappe.throw(_("This gate run already has a final decision. Create a new gate run for additional validation."))

def _seed(doc):
    existing_checks={row.check_code:row for row in doc.checks}
    for category,code,title,kind,mandatory in CHECKS:
        row=existing_checks.get(code)
        if not row:
            doc.append("checks",{"category":category,"check_code":code,"title":title,"execution_type":kind,"mandatory":mandatory,"status":"Pending"})
        elif row.status=="Pending":
            row.category=category; row.title=title; row.execution_type=kind; row.mandatory=mandatory
    existing_signoffs={row.department for row in doc.signoffs}
    for department in REQUIRED_SIGNOFFS:
        if department not in existing_signoffs:
            doc.append("signoffs",{"department":department,"status":"Pending"})

def _check(doc, code, status, measured=None, threshold=None, details=None):
    row=next((x for x in doc.checks if x.check_code==code),None)
    if not row: return
    row.status=status; row.measured_value=str(measured if measured is not None else ""); row.threshold=str(threshold or "")
    row.details=details or ""; row.checked_at=now_datetime(); row.checked_by=frappe.session.user

def _property_filter(alias, property_name):
    return (f" and {alias}.property=%s", [property_name]) if property_name else ("",[])

@frappe.whitelist()
def create_gate_run(property=None, environment_name="Staging", release_manifest=None, reconciliation_from_date=None, reconciliation_to_date=None, expected_frappe_version=None, expected_erpnext_version=None, expected_image_digest=None):
    _require_manager(); _validate_property(property)
    if not property and not is_privileged(): frappe.throw(_("Only System Manager may create a consolidated production gate."),frappe.PermissionError)
    if not release_manifest: frappe.throw(_("A frozen release manifest is required."))
    manifest=frappe.get_doc("Hotel Release Manifest",release_manifest)
    if manifest.status!="Frozen": frappe.throw(_("Release manifest must be frozen before creating a gate run."))
    if manifest.release_version!=__version__: frappe.throw(_("Release manifest does not match the installed application version."))
    settings=frappe.get_single("Hotel PMS Settings")
    doc=frappe.get_doc({"doctype":"Hotel Production Gate Run","property":property,"environment_name":environment_name,"release_version":__version__,"release_manifest":manifest.name,"expected_source_fingerprint":manifest.source_fingerprint,"expected_artifact_sha256":manifest.artifact_sha256,"expected_frappe_version":manifest.frappe_version,"expected_erpnext_version":manifest.erpnext_version,"expected_image_digest":manifest.image_digest,"reconciliation_from_date":reconciliation_from_date,"reconciliation_to_date":reconciliation_to_date,"target_rpo_minutes":cint(settings.get("production_target_rpo_minutes") or 1440),"target_rto_minutes":cint(settings.get("production_target_rto_minutes") or 240)})
    _seed(doc); doc.insert(ignore_permissions=True); return doc.as_dict()

@frappe.whitelist()
def execute_automated_checks(run_name, from_date=None, to_date=None):
    _require_manager(); doc=frappe.get_doc("Hotel Production Gate Run",run_name); _validate_property(doc.property); _ensure_gate_open(doc)
    _seed(doc); doc.status="Running"; doc.started_at=doc.started_at or now_datetime()
    settings=frappe.get_single("Hotel PMS Settings"); max_variance=flt(settings.get("production_max_accounting_variance") or 1)
    from_date=from_date or doc.reconciliation_from_date; to_date=to_date or doc.reconciliation_to_date
    try:
        import frappe as frappe_pkg, erpnext as erpnext_pkg
        apps=frappe.get_installed_apps(); doc.actual_frappe_version=getattr(frappe_pkg,"__version__",""); doc.actual_erpnext_version=getattr(erpnext_pkg,"__version__",""); doc.actual_image_digest=getattr(frappe.conf,"hotel_pms_image_digest",None) or os.getenv("HOTEL_PMS_IMAGE_DIGEST") or ""
        required=all(a in apps for a in ("frappe","erpnext","hotel_pms"))
        pinned=bool(doc.expected_frappe_version and doc.expected_erpnext_version and doc.expected_image_digest)
        match=pinned and doc.actual_frappe_version==doc.expected_frappe_version and doc.actual_erpnext_version==doc.expected_erpnext_version and doc.actual_image_digest==doc.expected_image_digest
        details={"apps":apps,"frappe":{"expected":doc.expected_frappe_version,"actual":doc.actual_frappe_version},"erpnext":{"expected":doc.expected_erpnext_version,"actual":doc.actual_erpnext_version},"image_digest":{"expected":doc.expected_image_digest,"actual":doc.actual_image_digest}}
        _check(doc,"APP_VERSION","Passed" if required and match else "Failed",__version__,"exact pinned versions and image digest",json.dumps(details))
    except Exception as e:_check(doc,"APP_VERSION","Failed",details=str(e))
    validation=validation_gate_results(doc)
    manifest=validation["manifest"]
    doc.actual_source_fingerprint=(manifest.get("environment") or {}).get("source_fingerprint")
    doc.actual_artifact_sha256=(manifest.get("environment") or {}).get("artifact_sha256")
    _check(doc,"MANIFEST_INTEGRITY","Passed" if manifest.get("passed") else "Failed",doc.actual_source_fingerprint,doc.expected_source_fingerprint,json.dumps(manifest,default=str))
    rehearsal_codes={"Blank Install":"BLANK_INSTALL_REHEARSAL","Upgrade":"UPGRADE_REHEARSAL","Concurrency":"CONCURRENCY_REHEARSAL","Security":"SECURITY_REHEARSAL","Restore":"RESTORE_REHEARSAL","Rollback":"ROLLBACK_REHEARSAL","Performance":"PERFORMANCE_REHEARSAL","Smoke":"SMOKE_REHEARSAL"}
    for run_type,code in rehearsal_codes.items():
        result=validation["rehearsals"].get(run_type) or {}
        record=result.get("record") or {}
        _check(doc,code,"Passed" if result.get("passed") else "Failed",record.get("name") or "missing",f"Passed {run_type} for exact source/image",json.dumps(record,default=str))
    parallel=validation.get("parallel") or {}
    parallel_status=validation.get("parallel_status")
    _check(doc,"PARALLEL_RECON","Passed" if parallel_status=="Passed" else ("Warning" if parallel_status=="Warning" else "Failed"),parallel.get("name") or "missing","latest batch Passed with no warnings/failures",json.dumps(parallel,default=str))
    from hotel_pms.staging_execution import latest_matching_evidence
    for evidence_code in ("STAGING_PREFLIGHT","RECON_SNAPSHOT","CUTOVER_BUNDLE"):
        evidence=latest_matching_evidence(doc.name,evidence_code)
        metadata=(evidence or {}).get("metadata") or {}
        artifact_match=bool(evidence and evidence.get("matches_current_environment"))
        content_pass=True
        if evidence_code=="STAGING_PREFLIGHT": content_pass=(metadata.get("summary") or {}).get("status")=="Passed"
        elif evidence_code=="RECON_SNAPSHOT": content_pass=metadata.get("status")=="Passed"
        passed=artifact_match and content_pass
        _check(doc,evidence_code,"Passed" if passed else "Failed",(evidence or {}).get("name") or "missing","matching immutable evidence for exact source/image",json.dumps(evidence or {},default=str))
    try: frappe.db.sql("select 1"); _check(doc,"DATABASE","Passed","OK","select 1")
    except Exception as e:_check(doc,"DATABASE","Failed",details=str(e))
    heartbeat=settings.get("last_worker_heartbeat"); age=(now_datetime()-frappe.utils.get_datetime(heartbeat)).total_seconds()/60 if heartbeat else 999999
    paused=cint(getattr(frappe.conf,"pause_scheduler",0)); _check(doc,"SCHEDULER","Passed" if age<15 and not paused else "Failed",round(age,2),"<15 minutes and scheduler active",f"pause_scheduler={paused}")
    backups=frappe.get_all("Hotel Backup Verification",fields=["name","backup_created_at","verified_at","verification_status"],order_by="verified_at desc",limit=1)
    backup_age=(now_datetime()-frappe.utils.get_datetime(backups[0].backup_created_at)).total_seconds()/60 if backups else 999999
    max_age=min(flt(settings.get("backup_freshness_hours") or 24)*60, flt(doc.target_rpo_minutes or 1440))
    doc.measured_rpo_minutes=round(backup_age,1) if backup_age<999999 else None
    _check(doc,"BACKUP_FRESHNESS",threshold_status(backup_age,max_age),round(backup_age,1),f"<={max_age} minutes")
    verified=bool(backups and backups[0].verification_status=="Verified")
    _check(doc,"BACKUP_CHECKSUM","Passed" if verified else "Failed",backups[0].name if backups else "none","latest backup verification")
    pf,pv=_property_filter("s",doc.property); sync=frappe.db.sql(f"select count(*) from `tabHotel ERP Sync Log` s where s.status in ('Failed','In Progress'){pf}",pv)[0][0]
    _check(doc,"SYNC_QUEUE","Passed" if sync==0 else "Failed",sync,"0 failed/in-progress")
    pf,pv=_property_filter("w",doc.property); dead=frappe.db.sql(f"select count(*) from `tabHotel Webhook Delivery` w where w.status='Dead Letter'{pf}",pv)[0][0]
    _check(doc,"WEBHOOK_DLQ","Passed" if dead==0 else "Failed",dead,"0 dead letters")
    from hotel_pms.platform import get_access_review
    access=get_access_review(); _check(doc,"PROPERTY_ACCESS","Passed" if access['users_missing_property']==0 else "Failed",access['users_missing_property'],"0 users missing property",json.dumps(access,default=str))
    acct=accounting_reconciliation(doc.property,from_date,to_date,max_variance); _check(doc,"ACCOUNTING_RECON","Passed" if not acct['blockers'] else "Failed",acct['variance'],f"<={max_variance}",json.dumps(acct,default=str))
    _check(doc,"CASHIER_RECON","Passed" if acct['open_cashier_variances']==0 else "Failed",acct['open_cashier_variances'],"0 unresolved shifts")
    stock=stock_reconciliation(doc.property,from_date,to_date); _check(doc,"STOCK_RECON","Passed" if not stock['blockers'] else "Failed",stock['blockers'],"0 blockers",json.dumps(stock,default=str))
    sec=public_security_check(doc.property); _check(doc,"PUBLIC_SECURITY","Passed" if not sec['blockers'] else "Failed",sec['blockers'],"0 blockers",json.dumps(sec,default=str))
    _update_summary(doc); doc.flags.production_gate_internal_update=True; doc.save(ignore_permissions=True); return doc.as_dict()

def accounting_reconciliation(property_name=None, from_date=None, to_date=None, max_variance=1):
    from_date=getdate(from_date or add_to_date(nowdate(),days=-30)); to_date=getdate(to_date or nowdate())
    sources=(("Hotel Folio","Hotel Folio Charge"),("Hotel Group Folio","Hotel Group Folio Charge"),("Hotel City Ledger Folio","Hotel City Ledger Charge"))
    totals={}; invalid_links=[]
    for parent_dt, child_dt in sources:
        pf=" and p.property=%s" if property_name else ""; vals=[from_date,to_date]+([property_name] if property_name else [])
        rows=frappe.db.sql(f"""select c.sales_invoice, sum(coalesce(nullif(c.gross_amount,0),c.amount)) charge_total from `tab{child_dt}` c inner join `tab{parent_dt}` p on p.name=c.parent where c.posting_date between %s and %s and coalesce(c.is_void,0)=0 and coalesce(c.is_already_invoiced,0)=1 {pf} group by c.sales_invoice""",vals,as_dict=True)
        for r in rows:
            if not r.sales_invoice: invalid_links.append({"source":child_dt,"invoice":None,"reason":"invoiced flag without invoice"}); continue
            totals[r.sales_invoice]=totals.get(r.sales_invoice,0)+flt(r.charge_total)
    mismatches=[]; total_variance=0.0
    for invoice, charge_total in totals.items():
        inv=frappe.db.get_value("Sales Invoice",invoice,["docstatus","grand_total"],as_dict=True)
        if not inv or inv.docstatus!=1: invalid_links.append({"invoice":invoice,"reason":"missing or not submitted"}); continue
        variance=float(money_variance(charge_total,inv.grand_total)); total_variance+=variance
        if variance>float(max_variance): mismatches.append({"invoice":invoice,"charge_total":charge_total,"invoice_total":inv.grand_total,"variance":variance})
    rpf=" and r.property=%s" if property_name else ""; rvals=[from_date,to_date]+([property_name] if property_name else [])
    deposits=frappe.db.sql(f"""select r.name,r.deposit_received,r.deposit_refunded,
      coalesce(sum(case when pe.custom_hotel_transaction_type='Deposit' and pe.docstatus=1 then coalesce(pe.received_amount,pe.paid_amount) else 0 end),0) actual_received,
      coalesce(sum(case when pe.custom_hotel_transaction_type='Refund' and pe.docstatus=1 then coalesce(pe.paid_amount,pe.received_amount) else 0 end),0) actual_refunded
      from `tabHotel Reservation` r left join `tabPayment Entry` pe on pe.custom_hotel_reservation=r.name
      where r.arrival_date between %s and %s {rpf} group by r.name,r.deposit_received,r.deposit_refunded""",rvals,as_dict=True)
    deposit_mismatches=[]
    for r in deposits:
        rv=float(money_variance(r.deposit_received,r.actual_received)); fv=float(money_variance(r.deposit_refunded,r.actual_refunded)); total_variance+=rv+fv
        if rv>float(max_variance) or fv>float(max_variance): deposit_mismatches.append(dict(r,received_variance=rv,refunded_variance=fv))
    spf=" and s.property=%s" if property_name else ""; svals=([property_name] if property_name else [])
    settlements=frappe.db.sql(f"""select s.name,s.status,s.purchase_invoice,pi.docstatus,pi.outstanding_amount from `tabHotel Travel Agent Settlement` s left join `tabPurchase Invoice` pi on pi.name=s.purchase_invoice where s.status in ('Invoiced','Paid') {spf}""",svals,as_dict=True)
    settlement_mismatches=[dict(x) for x in settlements if not x.purchase_invoice or x.docstatus!=1 or (x.status=='Paid' and flt(x.outstanding_amount)>float(max_variance))]
    pf=" and s.property=%s" if property_name else ""; vals=[property_name] if property_name else []
    open_variances=frappe.db.sql(f"select count(*) from `tabHotel Cashier Shift` s where s.status in ('Closing Review','Open') and abs(coalesce(s.variance,0))>0 {pf}",vals)[0][0]
    city_outstanding=frappe.db.sql(f"""select coalesce(sum(si.outstanding_amount),0) from `tabSales Invoice` si inner join `tabHotel City Ledger Folio` f on f.name=si.custom_hotel_city_ledger_folio where si.docstatus=1 {('and f.property=%s' if property_name else '')}""",([property_name] if property_name else []))[0][0] if frappe.get_meta('Sales Invoice').has_field('custom_hotel_city_ledger_folio') else 0
    blockers=len(mismatches)+len(invalid_links)+len(deposit_mismatches)+len(settlement_mismatches)+int(open_variances)
    return {"from_date":str(from_date),"to_date":str(to_date),"variance":round(total_variance,2),"mismatches":mismatches[:50],"invalid_links":invalid_links[:50],"deposit_mismatches":deposit_mismatches[:50],"travel_agent_mismatches":settlement_mismatches[:50],"city_ledger_outstanding":flt(city_outstanding),"open_cashier_variances":open_variances,"blockers":blockers}

def stock_reconciliation(property_name=None, from_date=None, to_date=None):
    from_date=getdate(from_date or add_to_date(nowdate(),days=-30)); to_date=getdate(to_date or nowdate())
    pf=" and o.property=%s" if property_name else ""; vals=[from_date,to_date]+([property_name] if property_name else [])
    rows=frappe.db.sql(f"""select s.name split_name,s.restaurant_order,s.erpnext_document_type,s.erpnext_document,s.status split_status,
        coalesce(pi.docstatus,si.docstatus) docstatus,coalesce(pi.update_stock,si.update_stock,0) update_stock,
        x.inventory_posting_policy
        from `tabHotel Restaurant Bill Split` s
        inner join `tabHotel Restaurant Order` o on o.name=s.restaurant_order
        inner join `tabHotel Outlet` x on x.name=o.outlet
        left join `tabPOS Invoice` pi on s.erpnext_document_type='POS Invoice' and pi.name=s.erpnext_document
        left join `tabSales Invoice` si on s.erpnext_document_type='Sales Invoice' and si.name=s.erpnext_document
        where o.order_date between %s and %s {pf} and s.status='Submitted'""",vals,as_dict=True)
    invalid=[]; missing_sle=0; checked_recipe_orders=set(); recipe_ticket_blockers=[]
    for r in rows:
        if r.docstatus!=1:
            invalid.append(dict(r,reason="ERPNext billing document is not submitted")); continue
        policy=r.inventory_posting_policy or "ERPNext POS Finished Goods"
        if policy=="ERPNext POS Finished Goods":
            if not r.update_stock:
                invalid.append(dict(r,reason="Finished-goods policy requires invoice update_stock")); continue
            item_table="POS Invoice Item" if r.erpnext_document_type=="POS Invoice" else "Sales Invoice Item"
            stock_items=frappe.db.sql(f"""select count(*) from `tab{item_table}` ii inner join `tabItem` i on i.name=ii.item_code where ii.parent=%s and i.is_stock_item=1""",r.erpnext_document)[0][0]
            if stock_items and not frappe.db.exists("Stock Ledger Entry",{"voucher_type":r.erpnext_document_type,"voucher_no":r.erpnext_document,"is_cancelled":0}): missing_sle+=1
        elif policy=="Recipe Material Issue":
            if r.update_stock:
                invalid.append(dict(r,reason="Recipe policy must disable invoice update_stock to avoid double stock")); continue
            if r.restaurant_order in checked_recipe_orders: continue
            checked_recipe_orders.add(r.restaurant_order)
            tickets=frappe.get_all("Hotel Kitchen Ticket",filters={"restaurant_order":r.restaurant_order,"status":["!=","Cancelled"]},fields=["name","stock_posting_status","stock_entry"])
            for ticket in tickets:
                if ticket.stock_posting_status=="Not Required": continue
                if ticket.stock_posting_status!="Submitted" or not ticket.stock_entry:
                    recipe_ticket_blockers.append({"order":r.restaurant_order,"ticket":ticket.name,"reason":ticket.stock_posting_status}); continue
                if frappe.db.get_value("Stock Entry",ticket.stock_entry,"docstatus")!=1:
                    recipe_ticket_blockers.append({"order":r.restaurant_order,"ticket":ticket.name,"reason":"Stock Entry not submitted"}); continue
                if not frappe.db.exists("Stock Ledger Entry",{"voucher_type":"Stock Entry","voucher_no":ticket.stock_entry,"is_cancelled":0}):
                    recipe_ticket_blockers.append({"order":r.restaurant_order,"ticket":ticket.name,"reason":"Missing Stock Ledger Entry"})
        else:
            if r.update_stock:
                invalid.append(dict(r,reason="No Stock Posting policy must keep invoice update_stock disabled"))
    blockers=len(invalid)+missing_sle+len(recipe_ticket_blockers)
    return {"submitted_restaurant_splits":len(rows),"invalid_documents":invalid[:50],"missing_stock_ledger":missing_sle,"recipe_ticket_blockers":recipe_ticket_blockers[:50],"blockers":blockers}


def public_security_check(property_name=None):
    settings=frappe.get_single("Hotel PMS Settings"); blockers=[]; warnings=[]
    if cint(settings.enable_public_booking):
        props=frappe.get_all("Hotel Property",filters={"enabled":1,"public_booking_enabled":1,**({"name":property_name} if property_name else {})},fields=["name","public_slug","public_terms","public_privacy_notice","default_hotel_tax_profile"])
        for p in props:
            for field in ("public_slug","public_terms","public_privacy_notice","default_hotel_tax_profile"):
                if not p.get(field): blockers.append(f"{p.name}: missing {field}")
    if cint(settings.enable_outbound_webhooks) and not frappe.get_all("Hotel Webhook Subscription",filters={"enabled":1},limit=1): warnings.append("Webhooks enabled without active subscription")
    return {"blockers":blockers,"warnings":warnings,"public_booking":cint(settings.enable_public_booking),"outbound_webhooks":cint(settings.enable_outbound_webhooks)}

@frappe.whitelist()
def record_manual_check(run_name,check_code,status,evidence_url=None,details=None,measured_value=None):
    _require_manager(); doc=frappe.get_doc("Hotel Production Gate Run",run_name); _validate_property(doc.property); _ensure_gate_open(doc)
    if status not in ("Passed","Warning","Failed","Not Applicable"): frappe.throw(_("Invalid status."))
    row=next((x for x in doc.checks if x.check_code==check_code and x.execution_type=="Manual"),None)
    if not row: frappe.throw(_("Manual check not found."))
    if status in ("Passed","Not Applicable") and not (evidence_url or details): frappe.throw(_("Evidence or details are required."))
    evidence=create_validation_evidence(run_name,check_code,"URL" if evidence_url else "Text",external_url=evidence_url,description=details,metadata_json={"status":status,"measured_value":measured_value})
    row.status=status; row.evidence_url=f"/app/hotel-validation-evidence/{evidence.name}"; row.details=details; row.measured_value=measured_value; row.checked_at=now_datetime(); row.checked_by=frappe.session.user
    if check_code=="RESTORE_DRILL" and measured_value:
        try:
            doc.measured_rto_minutes=flt(measured_value)
            if status=="Passed" and doc.measured_rto_minutes>flt(doc.target_rto_minutes): row.status="Failed"; row.details=(details or "")+"\nMeasured RTO exceeds target."
        except Exception: pass
    _update_summary(doc); doc.flags.production_gate_internal_update=True; doc.save(ignore_permissions=True); return doc.as_dict()

@frappe.whitelist()
def submit_signoff(run_name,department,status,comments=None):
    roles=set(frappe.get_roles())
    if not is_privileged() and not roles.intersection(SIGNOFF_ROLES.get(department,set())): frappe.throw(_("Your role cannot sign for this department."),frappe.PermissionError)
    doc=frappe.get_doc("Hotel Production Gate Run",run_name); _validate_property(doc.property); _ensure_gate_open(doc)
    row=next((x for x in doc.signoffs if x.department==department),None)
    if not row: frappe.throw(_("Department sign-off not found."))
    if status not in ("Approved","Rejected"): frappe.throw(_("Invalid sign-off status."))
    row.status=status; row.approver=frappe.session.user; row.signed_at=now_datetime(); row.comments=comments
    _update_summary(doc); doc.flags.production_gate_internal_update=True; doc.save(ignore_permissions=True); return doc.as_dict()

@frappe.whitelist()
def decide_go_live(run_name,decision,notes=None):
    if not is_privileged(): frappe.throw(_("Only System Manager may make the final go-live decision."),frappe.PermissionError)
    doc=frappe.get_doc("Hotel Production Gate Run",run_name)
    previous=doc.go_live_decision or "Pending"
    if decision not in ("Go","No-Go","Rollback"): frappe.throw(_("Invalid decision."))
    if previous!="Pending" and not (previous=="Go" and decision=="Rollback"):
        frappe.throw(_("The final decision is immutable. Only a Rollback may follow a Go decision."))
    _update_summary(doc)
    if decision=="Go" and doc.status!="Approved": frappe.throw(_("All mandatory checks and department sign-offs must be approved before Go."))
    if decision=="Rollback" and previous!="Go": frappe.throw(_("Rollback can only follow a Go decision."))
    evidence=create_validation_evidence(run_name,"FINAL_DECISION","Text",description=notes or decision,metadata_json={"previous":previous,"decision":decision})
    doc.go_live_decision=decision; doc.decision_by=frappe.session.user; doc.decision_at=now_datetime(); doc.decision_notes=f"{notes or ''}\nEvidence: {evidence.name}".strip()
    doc.promotion_status="Eligible" if decision=="Go" and doc.status=="Approved" else "Not Eligible"
    if decision=="Rollback" and doc.release_manifest:
        manifest=frappe.get_doc("Hotel Release Manifest",doc.release_manifest)
        if manifest.status in ("Frozen","Promotion Prepared","Promoted"):
            manifest.status="Revoked"; manifest.notes="\n".join(filter(None,[manifest.notes,f"Revoked after rollback decision on {doc.name}: {notes or ''}"]))
            manifest.flags.validation_internal_update=True; manifest.save(ignore_permissions=True)
    doc.completed_at=now_datetime(); doc.flags.production_gate_internal_update=True; doc.save(ignore_permissions=True); return doc.as_dict()

def _update_summary(doc):
    s=summarize_checks([x.as_dict() for x in doc.checks]); doc.blocker_count=s['blockers']; doc.warning_count=s['warnings']; doc.passed_count=s['passed']; doc.status=gate_status([x.as_dict() for x in doc.checks],[x.as_dict() for x in doc.signoffs]); doc.promotion_status=doc.promotion_status if doc.promotion_status in ('Promotion Prepared','Promoted') else ('Eligible' if doc.status=='Approved' and doc.go_live_decision=='Go' else 'Not Eligible')

@frappe.whitelist()
def get_gate_dashboard(run_name=None):
    _require_manager()
    if not run_name:
        rows=frappe.get_all("Hotel Production Gate Run",fields=["name","property","environment_name","release_version","release_manifest","status","blocker_count","warning_count","go_live_decision","promotion_status","modified"],order_by="modified desc",limit=20)
        return {"runs":rows}
    doc=frappe.get_doc("Hotel Production Gate Run",run_name); _validate_property(doc.property); return doc.as_dict()

def restore_smoke_check():
    required=("Hotel Property","Hotel Reservation","Hotel Folio","Hotel Room","Hotel PMS Settings")
    missing=[d for d in required if not frappe.db.exists("DocType",d)]
    return {"site":frappe.local.site,"app_version":__version__,"missing_doctypes":missing,"properties":frappe.db.count("Hotel Property"),"reservations":frappe.db.count("Hotel Reservation"),"ok":not missing}
