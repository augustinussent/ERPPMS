from __future__ import annotations
import hashlib,hmac,json,re
from datetime import timedelta
import requests
import frappe
from frappe import _
from frappe.utils import cint,now_datetime
from hotel_pms.sync import make_sync_key
from hotel_pms.adoption_rules import FINANCIAL_DOCTYPES

COMM_ROLES={"System Manager","Hotel Manager","Front Desk","Guest Services"}

def _require():
    if not set(frappe.get_roles()) & COMM_ROLES: frappe.throw(_("You do not have permission for guest communications."),frappe.PermissionError)

def normalize_phone(value:str|None)->str:
    digits=re.sub(r"\\D","",value or "")
    if digits.startswith("0"): digits="62"+digits[1:]
    return digits

def _connection(property_name:str):
    name=frappe.db.get_value("Hotel Channel Connection",{"property":property_name,"channel":"WhatsApp","provider":"Meta Cloud API","enabled":1,"is_default":1},"name")
    return frappe.get_doc("Hotel Channel Connection",name) if name else None

def _contact_phone(contact:str|None)->str|None:
    if not contact:return None
    rows=frappe.get_all("Contact Phone",filters={"parent":contact},fields=["phone","is_primary_phone","is_primary_mobile_no"],order_by="is_primary_mobile_no desc,is_primary_phone desc,idx asc",limit=5)
    for row in rows:
        phone=normalize_phone(row.phone)
        if phone:return phone
    return None

def _reservation_recipient(reservation):
    contact=reservation.communication_contact or reservation.guest_contact or reservation.booked_by_contact
    return contact,_contact_phone(contact)

def _template_name(connection,key):
    return {"booking_confirmation":"booking_confirmation_template","precheckin":"precheckin_template","payment_request":"payment_request_template"}.get(key)

def queue_template(*,property_name:str,to_number:str,template_key:str,variables:list[str],request_key:str,reservation:str|None=None,customer:str|None=None,contact:str|None=None,safe_summary:str|None=None,raw_link:str|None=None)->dict:
    if not cint(frappe.db.get_single_value("Hotel PMS Settings","enable_whatsapp_notifications") or 0): return {"queued":False,"reason":"disabled"}
    conn=_connection(property_name)
    if not conn:return {"queued":False,"reason":"no_connection"}
    field=_template_name(conn,template_key); template=conn.get(field) if field else None
    if not template:return {"queued":False,"reason":"template_not_configured"}
    phone=normalize_phone(to_number)
    if not phone:return {"queued":False,"reason":"no_phone"}
    key=make_sync_key("WHATSAPP",property_name,template_key,request_key)
    existing=frappe.db.get_value("Hotel Guest Message",{"request_key":key},"name")
    if existing:return {"queued":True,"message":existing,"already_created":True}
    msg=frappe.get_doc({"doctype":"Hotel Guest Message","property":property_name,"connection":conn.name,"direction":"Outbound","status":"Queued","message_type":"Template","to_number":phone,"customer":customer,"guest_contact":contact,"reservation":reservation,"template_name":template,"content":safe_summary or f"{template_key} template queued","secure_payload":json.dumps({"variables":[str(v) for v in variables],"raw_link":raw_link},ensure_ascii=False),"request_key":key,"queued_at":now_datetime()})
    try:
        msg.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        existing=frappe.db.get_value("Hotel Guest Message",{"request_key":key},"name")
        return {"queued":True,"message":existing,"already_created":True}
    frappe.enqueue("hotel_pms.communications.send_queued_message",message_name=msg.name,variables=[str(v) for v in variables],raw_link=raw_link,queue="short",enqueue_after_commit=True)
    return {"queued":True,"message":msg.name,"already_created":False}

def send_queued_message(message_name:str,variables:list[str]|None=None,raw_link:str|None=None)->dict:
    frappe.db.sql("select name from `tabHotel Guest Message` where name=%s for update",message_name)
    msg=frappe.get_doc("Hotel Guest Message",message_name)
    if msg.status in ("Sent","Delivered","Read"):return {"message":msg.name,"already_sent":True}
    if msg.status=="Sending" and msg.last_attempt_at:
        age=(now_datetime()-msg.last_attempt_at).total_seconds()
        if age<120:return {"message":msg.name,"already_sending":True}
    conn=frappe.get_doc("Hotel Channel Connection",msg.connection)
    if not conn.enabled: return _fail(msg,"CONNECTION_DISABLED","Connection is disabled")
    token=conn.get_password("access_token"); version=(conn.graph_api_version or "").strip(); phone_id=(conn.phone_number_id or "").strip()
    if not re.fullmatch(r"v\\d+\\.\\d+",version) or not phone_id.isdigit():return _fail(msg,"INVALID_CONNECTION","Invalid pinned API version or phone number ID")
    if variables is None:
        try:
            secure=json.loads(msg.get_password("secure_payload",raise_exception=False) or "{}")
        except Exception:
            secure={}
        variables=secure.get("variables") or []
        raw_link=secure.get("raw_link")
    if msg.message_type == "Text":
        payload={"messaging_product":"whatsapp","to":msg.to_number,"type":"text","text":{"body":(msg.content or "")[:4096]}}
    else:
        values=list(variables or [])
        if raw_link: values.append(raw_link)
        params=[{"type":"text","text":v[:1024]} for v in values]
        payload={"messaging_product":"whatsapp","to":msg.to_number,"type":"template","template":{"name":msg.template_name,"language":{"code":conn.template_language or "id"}}}
        if params: payload["template"]["components"]=[{"type":"body","parameters":params}]
    url=f"https://graph.facebook.com/{version}/{phone_id}/messages"
    msg.db_set({"status":"Sending","last_attempt_at":now_datetime(),"retry_count":cint(msg.retry_count)+1})
    try:
        response=requests.post(url,headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},json=payload,timeout=max(5,min(cint(conn.request_timeout_seconds or 15),60)))
        data=response.json() if response.content else {}
        if response.status_code>=400:
            error=(data.get("error") or {}) if isinstance(data,dict) else {}
            return _fail(msg,str(error.get("code") or response.status_code),str(error.get("message") or response.text)[:1000])
        provider_id=((data.get("messages") or [{}])[0]).get("id")
        msg.db_set({"status":"Sent","provider_message_id":provider_id,"sent_at":now_datetime(),"error_code":None,"error_message":None})
        msg.secure_payload=""
        msg.flags.ignore_permissions=True
        msg.save()
        conn.db_set({"last_message_at":now_datetime(),"last_error":None})
        if msg.reservation: frappe.db.set_value("Hotel Reservation",msg.reservation,{"last_guest_message_at":now_datetime()},update_modified=False)
        return {"message":msg.name,"provider_message_id":provider_id,"sent":True}
    except Exception as exc:
        return _fail(msg,"TRANSPORT",str(exc)[:1000])

def _fail(msg,code,message):
    limit=max(1,min(cint(frappe.db.get_single_value("Hotel PMS Settings","whatsapp_retry_limit") or 5),20))
    status="Dead Letter" if cint(msg.retry_count)>=limit else "Failed"
    msg.db_set({"status":status,"error_code":code,"error_message":message,"last_attempt_at":now_datetime()})
    if msg.connection:frappe.db.set_value("Hotel Channel Connection",msg.connection,"last_error",message,update_modified=False)
    return {"message":msg.name,"sent":False,"status":status,"error":message}

def process_message_queue()->dict:
    limit=max(1,min(cint(frappe.db.get_single_value("Hotel PMS Settings","whatsapp_retry_limit") or 5),20))
    rows=frappe.get_all("Hotel Guest Message",filters={"direction":"Outbound","status":["in",["Queued","Failed"]],"retry_count":["<",limit]},fields=["name"],order_by="creation asc",limit=50)
    queued=0
    for row in rows:
        frappe.enqueue("hotel_pms.communications.send_queued_message",message_name=row.name,queue="short")
        queued+=1
    return {"queued":queued}

def queue_booking_confirmation(reservation_name:str)->dict:
    if not cint(frappe.db.get_single_value("Hotel PMS Settings","whatsapp_auto_booking_confirmation") or 0):return {"queued":False,"reason":"auto_disabled"}
    reservation=frappe.get_doc("Hotel Reservation",reservation_name); contact,phone=_reservation_recipient(reservation)
    if not phone:return {"queued":False,"reason":"no_phone"}
    result=queue_template(property_name=reservation.property,to_number=phone,template_key="booking_confirmation",variables=[frappe.db.get_value("Customer",reservation.guest,"customer_name") or reservation.guest,reservation.property,str(reservation.arrival_date),str(reservation.departure_date)],request_key=f"booking-confirmation:{reservation.name}",reservation=reservation.name,customer=reservation.guest,contact=contact,safe_summary=f"Booking confirmation for {reservation.name}")
    if result.get("message") and not reservation.booking_confirmation_message:frappe.db.set_value("Hotel Reservation",reservation.name,"booking_confirmation_message",result["message"],update_modified=False)
    return result

def queue_precheckin_link(reservation_name:str,raw_token:str,request_key:str)->dict:
    if not cint(frappe.db.get_single_value("Hotel PMS Settings","whatsapp_auto_precheckin_link") or 0):return {"queued":False,"reason":"auto_disabled"}
    reservation=frappe.get_doc("Hotel Reservation",reservation_name); contact,phone=_reservation_recipient(reservation)
    if not phone:return {"queued":False,"reason":"no_phone"}
    link=frappe.utils.get_url(f"/hotel-checkin#token={raw_token}")
    return queue_template(property_name=reservation.property,to_number=phone,template_key="precheckin",variables=[frappe.db.get_value("Customer",reservation.guest,"customer_name") or reservation.guest],raw_link=link,request_key=request_key,reservation=reservation.name,customer=reservation.guest,contact=contact,safe_summary=f"Secure self check-in link sent for {reservation.name}")

def queue_payment_request(reservation_name:str,payment_url:str,amount,request_key:str)->dict:
    if not cint(frappe.db.get_single_value("Hotel PMS Settings","whatsapp_auto_payment_request") or 0):return {"queued":False,"reason":"auto_disabled"}
    reservation=frappe.get_doc("Hotel Reservation",reservation_name); contact,phone=_reservation_recipient(reservation)
    if not phone:return {"queued":False,"reason":"no_phone"}
    return queue_template(property_name=reservation.property,to_number=phone,template_key="payment_request",variables=[frappe.db.get_value("Customer",reservation.guest,"customer_name") or reservation.guest,str(amount)],raw_link=payment_url,request_key=request_key,reservation=reservation.name,customer=reservation.guest,contact=contact,safe_summary=f"Payment request sent for {reservation.name}")

def _raw_body()->bytes:
    request=frappe.local.request
    return request.get_data(cache=True) if request else b""

def _find_by_phone_id(phone_id):
    name=frappe.db.get_value("Hotel Channel Connection",{"phone_number_id":str(phone_id),"enabled":1},"name")
    return frappe.get_doc("Hotel Channel Connection",name) if name else None

def _verify_signature(conn,body:bytes):
    signature=(frappe.get_request_header("X-Hub-Signature-256") or "")
    secret=conn.get_password("app_secret")
    expected="sha256="+hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature,expected)

def _match_contact(phone:str):
    normalized=normalize_phone(phone); variants={normalized,"+"+normalized}
    if normalized.startswith("62"):variants.add("0"+normalized[2:])
    rows=frappe.get_all("Contact Phone",filters={"phone":["in",list(variants)]},pluck="parent",limit=10)
    return rows[0] if rows else None

def _customer_for_contact(contact):
    if not contact:return None
    return frappe.db.get_value("Dynamic Link",{"parent":contact,"parenttype":"Contact","link_doctype":"Customer"},"link_name")

def _active_reservation(contact,customer,property_name):
    if contact:
        name=frappe.db.get_value("Hotel Reservation",{"property":property_name,"status":"Checked In","guest_contact":contact},"name",order_by="actual_check_in_at desc")
        if name:return name
    if customer:
        return frappe.db.get_value("Hotel Reservation",{"property":property_name,"status":"Checked In","guest":customer},"name",order_by="actual_check_in_at desc")
    return None

@frappe.whitelist(allow_guest=True)
def meta_webhook():
    method=(frappe.local.request.method or "GET").upper()
    if method=="GET":
        verify=frappe.form_dict.get("hub.verify_token"); challenge=frappe.form_dict.get("hub.challenge"); mode=frappe.form_dict.get("hub.mode")
        for name in frappe.get_all("Hotel Channel Connection",filters={"enabled":1,"provider":"Meta Cloud API"},pluck="name"):
            conn=frappe.get_doc("Hotel Channel Connection",name)
            if hmac.compare_digest(conn.get_password("webhook_verify_token") or "",verify or "") and mode=="subscribe":
                from werkzeug.wrappers import Response
                conn.db_set("last_verified_at",now_datetime()); return Response(challenge,status=200,content_type="text/plain")
        from werkzeug.wrappers import Response
        return Response("verify token mismatch",status=403,content_type="text/plain")
    body=_raw_body(); payload=json.loads(body or b"{}")
    changes=[]
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []: changes.append(change.get("value") or {})
    processed=0
    for value in changes:
        phone_id=(value.get("metadata") or {}).get("phone_number_id"); conn=_find_by_phone_id(phone_id)
        if not conn or not _verify_signature(conn,body):frappe.throw(_("Invalid webhook signature."),frappe.PermissionError)
        for status in value.get("statuses") or []:
            provider_id=status.get("id"); state=status.get("status")
            name=frappe.db.get_value("Hotel Guest Message",{"provider_message_id":provider_id},"name")
            if name:
                fields={"delivered":"delivered_at","read":"read_at"}; values={"status":state.title()}
                if state in fields:values[fields[state]]=now_datetime()
                frappe.db.set_value("Hotel Guest Message",name,values,update_modified=False);processed+=1
        for item in value.get("messages") or []:
            provider_id=item.get("id")
            if frappe.db.exists("Hotel Guest Message",{"provider_message_id":provider_id}):continue
            sender=normalize_phone(item.get("from")); contact=_match_contact(sender); customer=_customer_for_contact(contact); reservation=_active_reservation(contact,customer,conn.property)
            content=((item.get("text") or {}).get("body") or f"[{item.get('type') or 'message'}]")[:2000]
            prop=frappe.db.get_value("Hotel Reservation",reservation,"property") if reservation else conn.property
            try:
                frappe.get_doc({"doctype":"Hotel Guest Message","property":prop,"connection":conn.name,"direction":"Inbound","status":"Received","message_type":"Text","from_number":sender,"to_number":normalize_phone(conn.display_number),"customer":customer,"guest_contact":contact,"reservation":reservation,"content":content,"provider_message_id":provider_id,"request_key":make_sync_key("WA-IN",provider_id),"received_at":now_datetime()}).insert(ignore_permissions=True)
                processed+=1
            except frappe.DuplicateEntryError:
                # Meta may redeliver the same webhook. The unique request key is
                # the final guard when two deliveries race each other.
                continue
    return {"processed":processed}

@frappe.whitelist()
def get_communication_console(property:str|None=None,limit:int=100)->dict:
    _require(); filters={}
    if property:
        frappe.get_doc("Hotel Property",property).check_permission("read")
        filters["property"]=property
    rows=frappe.get_list("Hotel Guest Message",filters=filters,fields=["name","property","direction","status","to_number","from_number","customer","reservation","content","template_name","creation","error_message","maintenance_ticket"],order_by="creation desc",limit_page_length=max(1,min(cint(limit or 100),300)))
    return {"messages":rows,"property":property}

@frappe.whitelist()
def send_staff_text(property:str,to_number:str,content:str,request_key:str,reservation:str|None=None)->dict:
    _require()
    frappe.get_doc("Hotel Property",property).check_permission("read")
    conn=_connection(property)
    if not conn:frappe.throw(_("No active default WhatsApp connection exists for this property."))
    if reservation and frappe.db.get_value("Hotel Reservation",reservation,"property") != property:
        frappe.throw(_("Reservation belongs to a different property."),frappe.PermissionError)
    phone=normalize_phone(to_number); text=(content or "").strip()
    if not phone or not text:frappe.throw(_("Phone number and message are required."))
    key=make_sync_key("WA-TEXT",property,request_key)
    existing=frappe.db.get_value("Hotel Guest Message",{"request_key":key},"name")
    if existing:return {"message":existing,"already_created":True}
    try:
        msg=frappe.get_doc({"doctype":"Hotel Guest Message","property":property,"connection":conn.name,"direction":"Outbound","status":"Queued","message_type":"Text","to_number":phone,"reservation":reservation,"content":text[:4096],"request_key":key,"queued_at":now_datetime()}).insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        existing=frappe.db.get_value("Hotel Guest Message",{"request_key":key},"name")
        return {"message":existing,"already_created":True}
    frappe.enqueue("hotel_pms.communications.send_queued_message",message_name=msg.name,queue="short",enqueue_after_commit=True)
    return {"message":msg.name,"queued":True,"already_created":False}

@frappe.whitelist()
def create_maintenance_from_message(message_name:str,subject:str|None=None)->dict:
    _require(); msg=frappe.get_doc("Hotel Guest Message",message_name);msg.check_permission("read")
    if msg.maintenance_ticket:return {"maintenance_ticket":msg.maintenance_ticket,"already_created":True}
    key=make_sync_key("WA-MAINT",msg.name);existing=frappe.db.get_value("Hotel Maintenance Ticket",{"idempotency_key":key},"name")
    if existing:msg.db_set("maintenance_ticket",existing);return {"maintenance_ticket":existing,"already_created":True}
    room=None
    if msg.reservation:
        rows=frappe.get_all("Hotel Reservation Room",filters={"parent":msg.reservation},pluck="room",limit=1);room=rows[0] if rows else None
    ticket=frappe.get_doc({"doctype":"Hotel Maintenance Ticket","property":msg.property,"subject":subject or f"WhatsApp guest request {msg.name}","source":"Guest Complaint","priority":"High - Guest Visible","problem_category":"Other","room":room,"reservation":msg.reservation,"reported_by":frappe.session.user,"description":msg.content,"idempotency_key":key}).insert(ignore_permissions=True)
    msg.db_set("maintenance_ticket",ticket.name);return {"maintenance_ticket":ticket.name,"already_created":False}
