from __future__ import annotations
import json
from collections import defaultdict
from decimal import Decimal
import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, get_datetime, getdate, now_datetime, nowdate
from hotel_pms.notifications import notify_roles
from hotel_pms.services_rules import allocation_conserves, derive_table_status, laundry_is_overdue, money
from hotel_pms.sync import make_sync_key

RESTAURANT_ROLES={"Restaurant Cashier","Restaurant Captain","Kitchen","Hotel Manager","System Manager"}
CAPTAIN_ROLES={"Restaurant Captain","Restaurant Cashier","Hotel Manager","System Manager"}
KITCHEN_ROLES={"Kitchen","Restaurant Captain","Hotel Manager","System Manager"}
LAUNDRY_ROLES={"Laundry","Front Desk","Hotel Manager","System Manager"}
GUEST_SERVICE_ROLES={"Guest Services","Front Desk","Hotel Manager","System Manager"}
HANDOVER_ROLES={"Front Desk","Housekeeping Supervisor","Engineering Supervisor","Restaurant Captain","Laundry","Guest Services","Hotel Manager","System Manager"}

def _roles(): return set(frappe.get_roles())
def _require(roles):
    if not (_roles() & roles): frappe.throw(_("You do not have permission for this operation."), frappe.PermissionError)
def _json(value):
    if isinstance(value,str):
        try:return json.loads(value)
        except json.JSONDecodeError: frappe.throw(_("Invalid JSON payload."))
    return value or {}
def _lock(doctype,name):
    rows=frappe.db.sql(f"select name from `tab{doctype}` where name=%s for update",name)
    if not rows: frappe.throw(_("{0} {1} was not found.").format(doctype,name))
    return frappe.get_doc(doctype,name)

def _set_table(table,order="__NO_CHANGE__",status=None):
    if not table:return
    values={}
    if order != "__NO_CHANGE__": values["active_order"]=order
    if status: values["status"]=status
    if values: frappe.db.set_value("Hotel Restaurant Table",table,values,update_modified=False)

def _next_kot_number(outlet):
    row=_lock("Hotel Outlet",outlet)
    today=getdate()
    if row.daily_kot_date!=today:
        row.daily_kot_date=today; row.daily_kot_counter=0
    row.daily_kot_counter=cint(row.daily_kot_counter)+1
    row.save(ignore_permissions=True)
    return row.daily_kot_counter

@frappe.whitelist()
def get_restaurant_console(outlet=None):
    _require(RESTAURANT_ROLES)
    outlet=outlet or frappe.db.get_single_value("Hotel PMS Settings","default_restaurant_outlet")
    tables=frappe.get_all("Hotel Restaurant Table",filters={"outlet":outlet,"enabled":1},fields=["name","table_name","dining_area","seats","status","active_order"],order_by="dining_area,table_name") if outlet else []
    open_orders=frappe.get_all("Hotel Restaurant Order",filters={"outlet":outlet,"status":["not in",["Billed","Cancelled"]]},fields=["name","service_type","table","room","guest_name","status","grand_total","ordered_at"],order_by="ordered_at asc") if outlet else []
    return {"outlet":outlet,"tables":tables,"orders":open_orders}

@frappe.whitelist()
def create_restaurant_order(payload,request_key):
    _require(CAPTAIN_ROLES)
    data=_json(payload); key=make_sync_key("RORDER",data.get("outlet"),request_key)
    existing=frappe.db.get_value("Hotel Restaurant Order",{"request_key":key},"name")
    if existing:return {"order":existing,"already_created":True}
    if data.get("table"):
        table = _lock("Hotel Restaurant Table", data.get("table"))
        if table.active_order and frappe.db.get_value("Hotel Restaurant Order", table.active_order, "status") not in ("Billed", "Cancelled"):
            frappe.throw(_("The selected table already has an active order."))
    doc=frappe.get_doc({"doctype":"Hotel Restaurant Order",**data,"request_key":key,"status":"Confirmed" if data.get("source")!="QR Ordering" else "Pending Confirmation"})
    doc.insert(ignore_permissions=True)
    if doc.table:_set_table(doc.table,doc.name,derive_table_status(doc.status))
    return {"order":doc.name,"already_created":False}

@frappe.whitelist()
def confirm_restaurant_order(order):
    _require(CAPTAIN_ROLES); doc=_lock("Hotel Restaurant Order",order)
    if doc.status in ("Confirmed","In Kitchen","Ready","Served","Bill Requested","Billed"): return {"order":doc.name,"status":doc.status,"already_processed":True}
    if doc.status not in ("Draft","Pending Confirmation"): frappe.throw(_("Order cannot be confirmed from status {0}.").format(doc.status))
    doc.status="Confirmed"; doc.confirmed_at=now_datetime(); doc.save(ignore_permissions=True)
    _set_table(doc.table,doc.name,derive_table_status(doc.status))
    return {"order":doc.name,"status":doc.status}

@frappe.whitelist()
def send_order_to_kitchen(order,request_key):
    _require(CAPTAIN_ROLES); doc=_lock("Hotel Restaurant Order",order)
    if doc.status not in ("Confirmed","In Kitchen"): frappe.throw(_("Confirm the order before sending it to the kitchen."))
    grouped=defaultdict(list)
    for row in doc.items:
        if row.status=="Ordered": grouped[row.kitchen_station or "Main Kitchen"].append(row)
    tickets=[]
    for station,items in grouped.items():
        key=make_sync_key("KOT",doc.name,station,request_key)
        existing=frappe.db.get_value("Hotel Kitchen Ticket",{"request_key":key},"name")
        if existing: tickets.append(existing); continue
        kot=frappe.get_doc({"doctype":"Hotel Kitchen Ticket","property":doc.property,"outlet":doc.outlet,"restaurant_order":doc.name,"kot_date":nowdate(),"daily_kot_number":_next_kot_number(doc.outlet),"kitchen_station":station,"sent_at":now_datetime(),"request_key":key})
        for item in items:
            kot.append("items",{"order_item_row":item.name,"item_code":item.item_code,"item_name":item.item_name,"qty":item.qty,"notes":item.notes})
        kot.insert(ignore_permissions=True); tickets.append(kot.name)
        for item in items: item.status="Sent"; item.kitchen_ticket=kot.name
    if grouped:
        doc.status="In Kitchen"; doc.save(ignore_permissions=True); _set_table(doc.table,doc.name,"In Kitchen")
        notify_roles(["Kitchen","Restaurant Captain","Hotel Manager"],property_name=doc.property,subject=_("New kitchen ticket for {0}").format(doc.name),message=_("{0} KOT(s) sent to kitchen.").format(len(tickets)),document_type=doc.doctype,document_name=doc.name,dedupe_key=f"kot:{doc.name}:{request_key}")
    return {"order":doc.name,"tickets":tickets}

@frappe.whitelist()
def update_kitchen_item(ticket,row_name,status):
    _require(KITCHEN_ROLES)
    if status not in ("Preparing","Ready","Served","Cancelled"): frappe.throw(_("Invalid kitchen status."))
    ticket_doc=_lock("Hotel Kitchen Ticket",ticket); row=next((r for r in ticket_doc.items if r.name==row_name),None)
    if not row: frappe.throw(_("Kitchen item was not found."))
    now=now_datetime(); row.status=status
    if status=="Preparing": row.started_at=row.started_at or now; ticket_doc.started_at=ticket_doc.started_at or now
    elif status=="Ready": row.ready_at=now
    elif status=="Served": row.served_at=now
    ticket_doc.status="Served" if all(r.status in ("Served","Cancelled") for r in ticket_doc.items) else ("Ready" if all(r.status in ("Ready","Served","Cancelled") for r in ticket_doc.items) else "Preparing")
    if ticket_doc.status=="Ready": ticket_doc.ready_at=now
    if ticket_doc.status=="Served": ticket_doc.served_at=now
    ticket_doc.save(ignore_permissions=True)
    order=frappe.get_doc("Hotel Restaurant Order",ticket_doc.restaurant_order)
    for item in order.items:
        if item.name==row.order_item_row: item.status=status
    statuses={r.status for r in order.items if r.status!="Cancelled"}
    if statuses and statuses <= {"Ready","Served"}: order.status="Ready"; order.ready_at=now
    if statuses and statuses <= {"Served"}: order.status="Served"; order.served_at=now
    order.save(ignore_permissions=True); _set_table(order.table,order.name,derive_table_status(order.status))
    return {"ticket":ticket_doc.name,"ticket_status":ticket_doc.status,"order_status":order.status}

@frappe.whitelist()
def get_kitchen_display(outlet=None,station=None):
    _require(KITCHEN_ROLES)
    filters={"status":["in",["New","Preparing","Ready"]]}
    if outlet: filters["outlet"]=outlet
    if station: filters["kitchen_station"]=station
    tickets=frappe.get_all("Hotel Kitchen Ticket",filters=filters,fields=["name","restaurant_order","outlet","kitchen_station","daily_kot_number","status","sent_at"],order_by="sent_at asc")
    for ticket in tickets: ticket["items"]=frappe.get_all("Hotel Kitchen Ticket Item",filters={"parent":ticket.name},fields=["name","item_name","qty","notes","status","started_at"])
    return {"tickets":tickets}

@frappe.whitelist()
def request_restaurant_bill(order):
    _require(CAPTAIN_ROLES); doc=_lock("Hotel Restaurant Order",order)
    if doc.status in ("Billed","Cancelled"): return {"order":doc.name,"status":doc.status,"already_processed":True}
    if doc.status not in ("Ready","Served","In Kitchen","Confirmed"): frappe.throw(_("Order cannot request a bill in status {0}.").format(doc.status))
    doc.status="Bill Requested"; doc.bill_requested_at=now_datetime(); doc.save(ignore_permissions=True); _set_table(doc.table,doc.name,"Bill Requested")
    return {"order":doc.name,"status":doc.status}

@frappe.whitelist()
def create_bill_splits(order,splits,request_key):
    _require(CAPTAIN_ROLES); data=_json(splits); order_doc=_lock("Hotel Restaurant Order",order)
    expected_keys=[make_sync_key("RSPLIT",order,request_key,idx) for idx,_ in enumerate(data,start=1)]
    retry_results=[frappe.db.get_value("Hotel Restaurant Bill Split", {"request_key": key}, "name") for key in expected_keys]
    if expected_keys and all(retry_results):
        return {"order":order,"splits":retry_results,"already_processed":True}
    existing_active = frappe.get_all("Hotel Restaurant Bill Split", filters={"restaurant_order": order, "status": ["!=", "Cancelled"]}, pluck="name")
    if existing_active:
        frappe.throw(_("Active bill splits already exist. Cancel them before creating a replacement split."))
    if order_doc.status not in ("Bill Requested","Served","Ready"): frappe.throw(_("Request the bill before splitting it."))
    allocations=defaultdict(Decimal); results=[]
    order_rows={r.name:r for r in order_doc.items if r.status!="Cancelled"}
    for idx,split in enumerate(data,start=1):
        key=expected_keys[idx-1]
        existing=frappe.db.get_value("Hotel Restaurant Bill Split",{"request_key":key},"name")
        if existing: results.append(existing); continue
        doc=frappe.get_doc({"doctype":"Hotel Restaurant Bill Split","restaurant_order":order,"split_label":split.get("split_label") or f"Split {idx}","customer":split.get("customer"),"settlement_type":split.get("settlement_type"),"mode_of_payment":split.get("mode_of_payment"),"folio":split.get("folio"),"city_ledger_folio":split.get("city_ledger_folio"),"request_key":key})
        for line in split.get("lines") or []:
            source=order_rows.get(line.get("order_item_row")); qty=Decimal(str(line.get("qty") or 0))
            if not source or qty<=0: frappe.throw(_("Invalid split line."))
            allocations[source.name]+=qty
            doc.append("lines",{"order_item_row":source.name,"item_code":source.item_code,"item_name":source.item_name,"qty":float(qty),"rate":source.rate})
        doc.insert(ignore_permissions=True); results.append(doc.name)
    for name,row in order_rows.items():
        if money(allocations.get(name,0)) != money(row.qty): frappe.throw(_("Split quantities must exactly allocate order item {0}.").format(row.item_name))
    return {"order":order,"splits":results}



@frappe.whitelist()
def create_default_bill_split(order, settlement_type, request_key, mode_of_payment=None, customer=None, folio=None, city_ledger_folio=None):
    _require(CAPTAIN_ROLES)
    doc = frappe.get_doc("Hotel Restaurant Order", order)
    lines = [{"order_item_row": row.name, "qty": row.qty} for row in doc.items if row.status != "Cancelled"]
    return create_bill_splits(order, [{"split_label":"Full Bill","settlement_type":settlement_type,"mode_of_payment":mode_of_payment,"customer":customer,"folio":folio or doc.folio,"city_ledger_folio":city_ledger_folio,"lines":lines}], request_key)


@frappe.whitelist()
def create_equal_bill_splits(order, shares, settlement_type, request_key, mode_of_payment=None):
    _require(CAPTAIN_ROLES)
    shares = cint(shares)
    if shares < 2 or shares > 20:
        frappe.throw(_("Equal split count must be between 2 and 20."))
    if settlement_type not in ("Cash", "Card", "UPI"):
        frappe.throw(_("Equal split currently supports direct settlements only. Use item allocation for room or city-ledger posting."))
    doc = frappe.get_doc("Hotel Restaurant Order", order)
    splits = [{"split_label": f"Split {i+1}", "settlement_type": settlement_type, "mode_of_payment": mode_of_payment, "lines": []} for i in range(shares)]
    for row in doc.items:
        if row.status == "Cancelled":
            continue
        item = frappe.get_cached_doc("Item", row.item_code)
        whole = frappe.db.get_value("UOM", item.stock_uom, "must_be_whole_number")
        if whole and flt(row.qty) % shares:
            frappe.throw(_("Item {0} uses a whole-number UOM and cannot be equally divided. Split by item instead.").format(row.item_name))
        base = Decimal(str(row.qty)) / Decimal(shares)
        running = Decimal("0")
        for idx in range(shares):
            qty = base if idx < shares-1 else Decimal(str(row.qty)) - running
            running += qty
            splits[idx]["lines"].append({"order_item_row": row.name, "qty": float(qty)})
    return create_bill_splits(order, splits, request_key)


def _taxes_template(outlet):
    profile=frappe.db.get_value("Hotel Outlet",outlet,"tax_profile")
    if profile:return frappe.db.get_value("Hotel Tax Profile",profile,"sales_taxes_template")
    return None


def _mirror_restaurant_split_to_folio(split_doc, order, invoice):
    if split_doc.settlement_type == "Room Posting":
        folio = frappe.get_doc("Hotel Folio", split_doc.folio)
        for idx, line in enumerate(split_doc.lines, start=1):
            key = make_sync_key("REST-FOLIO", split_doc.name, line.name or idx)
            if frappe.db.exists("Hotel Folio Charge", {"idempotency_key": key}):
                continue
            folio.append("charges", {"posting_date": nowdate(), "charge_type": "Food & Beverage", "item_code": line.item_code, "description": line.item_name or line.item_code, "qty": line.qty, "rate": line.rate, "room": order.room, "source_doctype": "Hotel Restaurant Bill Split", "source_name": split_doc.name, "idempotency_key": key, "sales_invoice": invoice.name})
        folio.save(ignore_permissions=True)
    elif split_doc.settlement_type == "City Ledger":
        folio = frappe.get_doc("Hotel City Ledger Folio", split_doc.city_ledger_folio)
        for idx, line in enumerate(split_doc.lines, start=1):
            key = make_sync_key("REST-CITY", split_doc.name, line.name or idx)
            if frappe.db.exists("Hotel City Ledger Charge", {"idempotency_key": key}):
                continue
            folio.append("charges", {"posting_date": nowdate(), "charge_category": "Food", "item_code": line.item_code, "description": line.item_name or line.item_code, "qty": line.qty, "rate": line.rate, "source_doctype": "Hotel Restaurant Bill Split", "source_name": split_doc.name, "idempotency_key": key, "sales_invoice": invoice.name})
        folio.save(ignore_permissions=True)

@frappe.whitelist()
def create_split_invoice(split,request_key,submit=0):
    _require({"Restaurant Cashier","Hotel Manager","System Manager"}); split_doc=_lock("Hotel Restaurant Bill Split",split)
    if split_doc.erpnext_document and frappe.db.exists(split_doc.erpnext_document_type,split_doc.erpnext_document):
        if frappe.db.get_value(split_doc.erpnext_document_type, split_doc.erpnext_document, "docstatus") < 2:
            return {"doctype":split_doc.erpnext_document_type,"name":split_doc.erpnext_document,"already_created":True}
        split_doc.erpnext_document_type = None
        split_doc.erpnext_document = None
        split_doc.status = "Draft"
        split_doc.save(ignore_permissions=True)
    order=frappe.get_doc("Hotel Restaurant Order",split_doc.restaurant_order); outlet=frappe.get_doc("Hotel Outlet",order.outlet)
    key=make_sync_key("RINVOICE",split_doc.name,request_key)
    if split_doc.settlement_type == "Complimentary":
        if not order.is_complimentary or not order.authorized_by:
            frappe.throw(_("Complimentary settlement requires an authorized complimentary order."))
        split_doc.status = "Submitted"
        split_doc.save(ignore_permissions=True)
        return {"doctype": None, "name": None, "already_created": False, "submitted": True}
    if split_doc.settlement_type in ("Cash","Card","UPI"):
        doctype="POS Invoice"; customer=split_doc.customer or order.customer or outlet.default_customer
        if not customer: frappe.throw(_("Customer or default walk-in customer is required."))
        if not outlet.pos_profile: frappe.throw(_("POS Profile is required for direct restaurant settlement."))
        doc=frappe.get_doc({"doctype":doctype,"company":outlet.company,"customer":customer,"is_pos":1,"pos_profile":outlet.pos_profile,"set_warehouse":outlet.warehouse,"update_stock":1,"posting_date":nowdate(),"custom_hotel_restaurant_order":order.name,"custom_hotel_restaurant_split":split_doc.name,"custom_hotel_sync_key":key,"custom_hotel_cashier_shift":frappe.db.get_value("Hotel Cashier Shift",{"property":order.property,"cashier":frappe.session.user,"status":"Open"},"name")})
        for line in split_doc.lines: doc.append("items",{"item_code":line.item_code,"qty":line.qty,"rate":line.rate,"warehouse":outlet.warehouse,"cost_center":outlet.cost_center,"income_account":outlet.income_account})
        if template:=_taxes_template(order.outlet): doc.taxes_and_charges=template
        doc.set_missing_values()
        doc.calculate_taxes_and_totals()
        doc.set("payments", [])
        if split_doc.mode_of_payment: doc.append("payments",{"mode_of_payment":split_doc.mode_of_payment,"amount":doc.rounded_total or doc.grand_total})
    else:
        doctype="Sales Invoice"
        if split_doc.settlement_type=="Room Posting":
            folio=frappe.get_doc("Hotel Folio",split_doc.folio); customer=folio.billing_customer
        elif split_doc.settlement_type=="City Ledger":
            folio=frappe.get_doc("Hotel City Ledger Folio",split_doc.city_ledger_folio); customer=folio.billing_customer
        else:
            customer=split_doc.customer or order.customer or outlet.default_customer
        doc=frappe.get_doc({"doctype":doctype,"company":outlet.company,"customer":customer,"posting_date":nowdate(),"update_stock":1,"set_warehouse":outlet.warehouse,"custom_hotel_restaurant_order":order.name,"custom_hotel_restaurant_split":split_doc.name,"custom_hotel_sync_key":key})
        if split_doc.settlement_type=="Room Posting": doc.custom_hotel_folio=split_doc.folio
        if split_doc.settlement_type=="City Ledger": doc.custom_hotel_city_ledger_folio=split_doc.city_ledger_folio
        for line in split_doc.lines: doc.append("items",{"item_code":line.item_code,"qty":line.qty,"rate":line.rate,"warehouse":outlet.warehouse,"cost_center":outlet.cost_center,"income_account":outlet.income_account})
    template=_taxes_template(order.outlet)
    if template and not doc.taxes_and_charges: doc.taxes_and_charges=template
    doc.insert(ignore_permissions=True)
    if split_doc.settlement_type in ("Room Posting", "City Ledger"):
        _mirror_restaurant_split_to_folio(split_doc, order, doc)
    if cint(submit): doc.submit()
    split_doc.erpnext_document_type=doctype; split_doc.erpnext_document=doc.name; split_doc.status="Submitted" if doc.docstatus==1 else "Invoice Draft Created"; split_doc.save(ignore_permissions=True)
    return {"doctype":doctype,"name":doc.name,"already_created":False,"submitted":doc.docstatus==1}

@frappe.whitelist()
def complete_restaurant_order(order):
    _require({"Restaurant Cashier","Hotel Manager","System Manager"}); doc=_lock("Hotel Restaurant Order",order)
    splits=frappe.get_all("Hotel Restaurant Bill Split",filters={"restaurant_order":order,"status":["!=","Cancelled"]},fields=["name","erpnext_document_type","erpnext_document"])
    if not splits: frappe.throw(_("Create at least one bill split before completing the order."))
    allocated = defaultdict(Decimal)
    for split in splits:
        for line in frappe.get_all("Hotel Restaurant Bill Split Line", filters={"parent": split.name}, fields=["order_item_row", "qty"]):
            allocated[line.order_item_row] += Decimal(str(line.qty or 0))
        settlement_type = frappe.db.get_value("Hotel Restaurant Bill Split", split.name, "settlement_type")
        if settlement_type == "Complimentary":
            continue
        if not split.erpnext_document or not frappe.db.exists(split.erpnext_document_type,split.erpnext_document): frappe.throw(_("Every non-complimentary split must have an ERPNext billing document."))
        if frappe.db.get_value(split.erpnext_document_type,split.erpnext_document,"docstatus")!=1: frappe.throw(_("Submit all ERPNext billing documents before completing the order."))
    for item in doc.items:
        if item.status != "Cancelled" and money(allocated.get(item.name, 0)) != money(item.qty):
            frappe.throw(_("Bill splits do not exactly allocate item {0}.").format(item.item_name))
    doc.status="Billed"; doc.pos_invoice_count=len(splits); doc.save(ignore_permissions=True); _set_table(doc.table,None,"Cleaning")
    return {"order":doc.name,"status":doc.status}

@frappe.whitelist(allow_guest=True,methods=["POST"])
def get_qr_menu(table_token):
    if not cint(frappe.db.get_single_value("Hotel PMS Settings", "enable_public_qr_ordering")):
        frappe.throw(_("Public QR ordering is disabled."))
    table=frappe.db.get_value("Hotel Restaurant Table",{"qr_token":table_token,"enabled":1},["name","outlet","table_name","status"],as_dict=True)
    if not table: frappe.throw(_("Dining table link is invalid."),frappe.PermissionError)
    active_order = frappe.db.get_value("Hotel Restaurant Table", table.name, "active_order")
    if active_order and frappe.db.get_value("Hotel Restaurant Order", active_order, "status") not in ("Billed", "Cancelled"):
        frappe.throw(_("This table already has an active order. Ask the captain to add items."))
    outlet=frappe.get_doc("Hotel Outlet",table.outlet)
    if not outlet.enabled or not outlet.allow_qr_ordering: frappe.throw(_("QR ordering is not enabled for this outlet."))
    items=frappe.get_all("Hotel Outlet Menu Item",filters={"outlet":outlet.name,"available":1,"allow_qr_ordering":1},fields=["name","item_code","menu_name","description","rate","image","preparation_minutes"],order_by="display_order,menu_name")
    for item in items:
        if (item.image or "").startswith("/private/"):
            item.image = None
    return {"table":table,"outlet":{"name":outlet.name,"outlet_name":outlet.outlet_name},"items":items}

@frappe.whitelist(allow_guest=True,methods=["POST"])
def submit_qr_order(table_token,payload,request_key):
    if not cint(frappe.db.get_single_value("Hotel PMS Settings", "enable_public_qr_ordering")):
        frappe.throw(_("Public QR ordering is disabled."))
    data=_json(payload); table_ref=frappe.db.get_value("Hotel Restaurant Table",{"qr_token":table_token,"enabled":1},["name","outlet"],as_dict=True)
    if not table_ref: frappe.throw(_("Dining table link is invalid."),frappe.PermissionError)
    table=_lock("Hotel Restaurant Table",table_ref.name)
    outlet=frappe.get_doc("Hotel Outlet",table.outlet)
    if not outlet.allow_qr_ordering: frappe.throw(_("QR ordering is disabled."))
    key=make_sync_key("QRORDER",table.name,request_key); existing=frappe.db.get_value("Hotel Restaurant Order",{"request_key":key},"name")
    if existing:return {"order":existing,"already_created":True}
    if table.active_order and frappe.db.get_value("Hotel Restaurant Order", table.active_order, "status") not in ("Billed", "Cancelled"):
        frappe.throw(_("This table already has an active order. Ask the captain to add items."))
    order=frappe.get_doc({"doctype":"Hotel Restaurant Order","property":outlet.property,"outlet":outlet.name,"service_type":"Dine In","table":table.name,"guest_name":(data.get("guest_name") or "Table Guest")[:140],"pax":cint(data.get("pax") or 1),"source":"QR Ordering","status":"Pending Confirmation","notes":data.get("notes"),"request_key":key})
    for requested in data.get("items") or []:
        menu=frappe.get_doc("Hotel Outlet Menu Item",requested.get("menu_item"))
        if menu.outlet!=outlet.name or not menu.available or not menu.allow_qr_ordering: frappe.throw(_("A selected menu item is unavailable."))
        qty=flt(requested.get("qty"));
        if qty<=0: frappe.throw(_("Menu quantity must be greater than zero."))
        order.append("items",{"menu_item":menu.name,"item_code":menu.item_code,"item_name":menu.menu_name,"qty":qty,"rate":menu.rate,"kitchen_station":menu.kitchen_station,"notes":requested.get("notes")})
    if not order.items: frappe.throw(_("Select at least one menu item."))
    order.insert(ignore_permissions=True); _set_table(table.name,order.name,"Occupied")
    notify_roles(["Restaurant Captain","Restaurant Cashier","Hotel Manager"],property_name=outlet.property,subject=_("QR order awaiting confirmation"),message=_("Order {0} from table {1} requires confirmation.").format(order.name,table.name),document_type=order.doctype,document_name=order.name,dedupe_key=f"qr:{key}")
    return {"order":order.name,"already_created":False}



@frappe.whitelist()
def cancel_restaurant_order(order, reason):
    _require(CAPTAIN_ROLES)
    if not reason:
        frappe.throw(_("Cancellation reason is required."))
    doc = _lock("Hotel Restaurant Order", order)
    if doc.status == "Cancelled":
        return {"order": doc.name, "already_processed": True}
    submitted = frappe.db.sql("""select count(*) from `tabHotel Restaurant Bill Split` s left join `tabPOS Invoice` p on p.name=s.erpnext_document and s.erpnext_document_type='POS Invoice' left join `tabSales Invoice` i on i.name=s.erpnext_document and s.erpnext_document_type='Sales Invoice' where s.restaurant_order=%s and (p.docstatus=1 or i.docstatus=1)""", order)[0][0]
    if submitted:
        frappe.throw(_("Cancel or return submitted ERPNext billing documents before cancelling the restaurant order."))
    doc.status = "Cancelled"
    doc.cancel_reason = reason
    for row in doc.items:
        if row.status != "Cancelled":
            row.status = "Cancelled"
            row.cancel_reason = reason
    doc.save(ignore_permissions=True)
    for ticket in frappe.get_all("Hotel Kitchen Ticket", filters={"restaurant_order": order, "status": ["!=", "Cancelled"]}, pluck="name"):
        frappe.db.set_value("Hotel Kitchen Ticket", ticket, "status", "Cancelled", update_modified=False)
    _set_table(doc.table, None, "Available")
    return {"order": doc.name, "status": doc.status}


@frappe.whitelist()
def update_table_reservation(reservation, status):
    _require(CAPTAIN_ROLES | {"Front Desk"})
    allowed = {"Confirmed", "Seated", "Completed", "No Show", "Cancelled"}
    if status not in allowed:
        frappe.throw(_("Invalid table-reservation status."))
    doc = _lock("Hotel Table Reservation", reservation)
    doc.status = status
    doc.save(ignore_permissions=True)
    table = frappe.get_doc("Hotel Restaurant Table", doc.table)
    if status == "Seated":
        if table.active_order and frappe.db.get_value("Hotel Restaurant Order", table.active_order, "status") not in ("Billed", "Cancelled"):
            frappe.throw(_("The table already has an active order."))
        _set_table(table.name, status="Occupied")
    elif status in ("Completed", "No Show", "Cancelled") and not table.active_order:
        _set_table(table.name, status="Available")
    else:
        _set_table(table.name, status="Reserved")
    return {"reservation": doc.name, "status": doc.status}


@frappe.whitelist()
def close_shift_handover(handover, next_shift_name=None, incoming_user=None, request_key=None):
    _require(HANDOVER_ROLES)
    doc = _lock("Hotel Shift Handover", handover)
    if doc.status == "Closed":
        return {"handover": doc.name, "already_processed": True}
    if doc.status not in ("Submitted", "Acknowledged"):
        frappe.throw(_("Submit or acknowledge the handover before closing it."))
    open_items = [row for row in doc.items if row.status in ("Open", "Monitoring")]
    next_doc = None
    if open_items:
        key = make_sync_key("HANDOVER-NEXT", doc.name, request_key or next_shift_name or "NEXT")
        existing = frappe.db.get_value("Hotel Shift Handover", {"request_key": key}, "name")
        if existing:
            next_doc = frappe.get_doc("Hotel Shift Handover", existing)
        else:
            next_doc = frappe.get_doc({"doctype":"Hotel Shift Handover","property":doc.property,"department":doc.department,"shift_date":nowdate(),"shift_name":next_shift_name or "Custom","outgoing_user":frappe.session.user,"incoming_user":incoming_user,"status":"Draft","summary":_("Carried forward from {0}").format(doc.name),"request_key":key})
            for row in open_items:
                next_doc.append("items", {"priority":row.priority,"subject":row.subject,"details":row.details,"source_doctype":row.source_doctype,"source_name":row.source_name,"owner_user":row.owner_user,"due_at":row.due_at,"status":"Open"})
            next_doc.insert(ignore_permissions=True)
        for row in open_items:
            row.status = "Carried Forward"
            row.carried_to = next_doc.name
    doc.status = "Closed"
    doc.save(ignore_permissions=True)
    return {"handover": doc.name, "next_handover": next_doc.name if next_doc else None}


@frappe.whitelist()
def get_laundry_console(property=None):
    _require(LAUNDRY_ROLES); property=property or frappe.db.get_single_value("Hotel PMS Settings","default_property")
    orders=frappe.get_all("Hotel Laundry Order",filters={"property":property,"status":["not in",["Billed","Cancelled"]]},fields=["name","reservation","room","status","requested_at","promised_ready_at","overdue","total_amount","source"],order_by="overdue desc,promised_ready_at asc")
    return {"property":property,"orders":orders}

@frappe.whitelist()
def update_laundry_status(order,status):
    _require(LAUNDRY_ROLES); allowed=["Pickup Scheduled","Picked Up","Counted","In Process","Ready","Returned","Billed","Cancelled"]
    if status not in allowed: frappe.throw(_("Invalid laundry status."))
    doc=_lock("Hotel Laundry Order",order); now=now_datetime(); doc.status=status
    if status=="Picked Up":doc.pickup_at=now
    if status=="Ready":doc.ready_at=now
    if status=="Returned":doc.returned_at=now
    doc.overdue=0 if status in ("Ready","Returned","Billed","Cancelled") else doc.overdue
    doc.save(ignore_permissions=True)
    if status == "Returned" and cint(frappe.db.get_single_value("Hotel PMS Settings", "auto_post_laundry_on_return")) and doc.order_type == "Guest":
        return post_laundry_to_folio(doc.name, make_sync_key("AUTO-LAUNDRY", doc.name))
    return {"order":doc.name,"status":doc.status}

@frappe.whitelist()
def post_laundry_to_folio(order,request_key):
    _require(LAUNDRY_ROLES); doc=_lock("Hotel Laundry Order",order)
    if doc.order_type!="Guest": return {"order":doc.name,"posted":False,"reason":"Non-billable order"}
    if doc.folio_posted:return {"order":doc.name,"posted":True,"already_processed":True}
    if doc.status not in ("Ready","Returned"): frappe.throw(_("Laundry can be posted after it is ready or returned."))
    if not doc.folio: frappe.throw(_("Hotel Folio is required."))
    if not doc.items: frappe.throw(_("Count laundry items before posting to the folio."))
    folio=frappe.get_doc("Hotel Folio",doc.folio)
    for idx,row in enumerate(doc.items,start=1):
        key=make_sync_key("LAUNDRY",doc.name,row.name or idx)
        if frappe.db.exists("Hotel Folio Charge",{"idempotency_key":key}):continue
        folio.append("charges",{"posting_date":nowdate(),"charge_type":"Laundry","item_code":row.item_code,"description":row.description,"qty":row.qty_sent,"rate":row.rate,"room":doc.room,"source_doctype":doc.doctype,"source_name":doc.name,"idempotency_key":key})
    folio.save(ignore_permissions=True); doc.folio_posted=1; doc.status="Billed"; doc.save(ignore_permissions=True)
    return {"order":doc.name,"posted":True,"folio":folio.name}

@frappe.whitelist()
def confirm_experience_booking(booking):
    _require(GUEST_SERVICE_ROLES); doc=_lock("Hotel Experience Booking",booking)
    if doc.status=="Confirmed":return {"booking":doc.name,"already_processed":True}
    if doc.status!="Requested":frappe.throw(_("Only requested bookings can be confirmed."))
    doc.status="Confirmed"; doc.save(ignore_permissions=True); return {"booking":doc.name,"status":doc.status}

@frappe.whitelist()
def post_experience_to_folio(booking,request_key):
    _require(GUEST_SERVICE_ROLES); doc=_lock("Hotel Experience Booking",booking)
    if doc.folio_posted:return {"booking":doc.name,"already_processed":True}
    if doc.status not in ("Confirmed","Completed"):frappe.throw(_("Confirm the experience before posting it."))
    if not doc.folio:frappe.throw(_("Hotel Folio is required."))
    exp=frappe.get_doc("Hotel Guest Experience",doc.experience); key=make_sync_key("EXPERIENCE",doc.name)
    folio=frappe.get_doc("Hotel Folio",doc.folio)
    if not frappe.db.exists("Hotel Folio Charge",{"idempotency_key":key}):
        folio.append("charges",{"posting_date":nowdate(),"charge_type":"Other","item_code":exp.item_code,"description":exp.experience_name,"qty":doc.participants,"rate":exp.price,"source_doctype":doc.doctype,"source_name":doc.name,"idempotency_key":key}); folio.save(ignore_permissions=True)
    doc.folio_posted=1; doc.save(ignore_permissions=True); return {"booking":doc.name,"folio":folio.name}

@frappe.whitelist()
def submit_shift_handover(handover):
    _require(HANDOVER_ROLES); doc=_lock("Hotel Shift Handover",handover)
    if doc.status!="Draft":return {"handover":doc.name,"status":doc.status,"already_processed":True}
    doc.status="Submitted"; doc.submitted_at=now_datetime(); doc.save(ignore_permissions=True)
    return {"handover":doc.name,"status":doc.status}

@frappe.whitelist()
def acknowledge_shift_handover(handover):
    _require(HANDOVER_ROLES); doc=_lock("Hotel Shift Handover",handover)
    if doc.status=="Acknowledged":return {"handover":doc.name,"already_processed":True}
    if doc.status!="Submitted":frappe.throw(_("Only submitted handovers can be acknowledged."))
    if doc.incoming_user and doc.incoming_user!=frappe.session.user and not ({"Hotel Manager","System Manager"}&_roles()):frappe.throw(_("This handover is assigned to another incoming user."))
    doc.status="Acknowledged"; doc.acknowledged_at=now_datetime(); doc.acknowledged_by=frappe.session.user; doc.save(ignore_permissions=True)
    return {"handover":doc.name,"status":doc.status}



def sync_restaurant_billing_document(doc, cancelled=False):
    split_name = getattr(doc, "custom_hotel_restaurant_split", None)
    order_name = getattr(doc, "custom_hotel_restaurant_order", None)
    if split_name and frappe.db.exists("Hotel Restaurant Bill Split", split_name):
        frappe.db.set_value("Hotel Restaurant Bill Split", split_name, {"status": "Draft" if cancelled else "Submitted", "erpnext_document_type": doc.doctype, "erpnext_document": doc.name}, update_modified=False)
    if order_name and frappe.db.exists("Hotel Restaurant Order", order_name):
        count = frappe.db.count("Hotel Restaurant Bill Split", {"restaurant_order": order_name, "status": "Submitted"})
        values = {"pos_invoice_count": count}
        if cancelled and frappe.db.get_value("Hotel Restaurant Order", order_name, "status") == "Billed":
            values["status"] = "Bill Requested"
        frappe.db.set_value("Hotel Restaurant Order", order_name, values, update_modified=False)

def monitor_guest_services():
    if not cint(frappe.db.get_single_value("Hotel PMS Settings", "laundry_overdue_notifications")):
        return
    now=now_datetime()
    for name in frappe.get_all("Hotel Laundry Order",filters={"status":["not in",["Ready","Returned","Billed","Cancelled"]],"promised_ready_at":["is","set"]},pluck="name"):
        doc=frappe.get_doc("Hotel Laundry Order",name); overdue=laundry_is_overdue(doc.status,get_datetime(doc.promised_ready_at),now)
        if overdue and not doc.overdue:
            doc.db_set("overdue",1,update_modified=False)
            notify_roles(["Laundry","Front Desk","Hotel Manager"],property_name=doc.property,subject=_("Laundry order overdue"),message=_("Laundry order {0} has passed its promised ready time.").format(doc.name),document_type=doc.doctype,document_name=doc.name,dedupe_key=f"laundry-overdue:{doc.name}")
