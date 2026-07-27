
from __future__ import annotations
import hashlib, json, secrets
from datetime import timedelta
from decimal import Decimal
import frappe
from frappe import _
from frappe.exceptions import DuplicateEntryError
from frappe.utils import add_days, cint, flt, get_datetime, getdate, now_datetime, nowdate, strip_html
from hotel_pms.guest_rules import blacklist_blocks, can_anonymize, normalize_email, normalize_phone, token_is_usable
from hotel_pms.sync import create_document_once, make_sync_key

PUBLIC_ACTIONS={"Guest Portal","Self Check-in","Cancellation","Payment","Privacy Request"}

def _payload(value):
    if isinstance(value,str):
        try:return json.loads(value)
        except json.JSONDecodeError: frappe.throw(_("Invalid JSON payload."))
    return value or {}

def _client_ip():
    req=getattr(frappe.local,"request",None)
    return (getattr(req,"headers",{}).get("X-Forwarded-For","").split(",")[0].strip() if req else "") or (getattr(req,"remote_addr","") if req else "")

def _user_agent():
    req=getattr(frappe.local,"request",None); return (getattr(req,"headers",{}).get("User-Agent","") if req else "")[:500]

def _rate_limit(bucket:str, limit:int=30, seconds:int=60):
    key=f"hotel-guest-rate:{bucket}:{_client_ip() or 'unknown'}"
    count=cint(frappe.cache.get_value(key) or 0)+1
    frappe.cache.set_value(key,count,expires_in_sec=seconds)
    if count>limit: frappe.throw(_("Too many requests. Please try again shortly."))

def _hash(raw:str)->str:return hashlib.sha256(raw.encode()).hexdigest()

def _plain(value):
    return strip_html(value or "").strip()

def issue_guest_token(*,reservation:str|None=None,customer:str|None=None,purpose:str="Guest Portal",valid_days:int|None=None,request_key:str|None=None,max_uses:int=0)->dict:
    if purpose not in PUBLIC_ACTIONS: frappe.throw(_("Unsupported guest token purpose."))
    days=cint(valid_days or frappe.db.get_single_value("Hotel PMS Settings","guest_portal_token_days") or 30)
    key=make_sync_key("GTOKEN",purpose,reservation or customer,request_key or secrets.token_hex(8))
    existing=frappe.db.get_value("Hotel Guest Access Token",{"request_key":key,"status":"Active"},["name","expires_at"],as_dict=True)
    if existing:
        return {"token_record":existing.name,"raw_token":None,"already_created":True,"expires_at":existing.expires_at}
    raw=secrets.token_urlsafe(32)
    profile=ensure_guest_profile(customer) if customer else None
    doc=frappe.get_doc({"doctype":"Hotel Guest Access Token","token_hash":_hash(raw),"purpose":purpose,"reservation":reservation,"customer":customer,"guest_profile":profile,"expires_at":now_datetime()+timedelta(days=days),"max_uses":max_uses,"request_key":key})
    doc.insert(ignore_permissions=True)
    if reservation: frappe.db.set_value("Hotel Reservation",reservation,{"guest_portal_status":"Active","guest_profile":profile},update_modified=False)
    return {"token_record":doc.name,"raw_token":raw,"already_created":False,"expires_at":doc.expires_at}

def validate_guest_token(raw_token:str,purpose:str|None=None,reservation:str|None=None,consume:bool=True):
    if not raw_token: frappe.throw(_("Guest access token is required."),frappe.PermissionError)
    row=frappe.db.get_value("Hotel Guest Access Token",{"token_hash":_hash(raw_token)},["name","purpose","reservation","customer","guest_profile","status","expires_at","usage_count","max_uses"],as_dict=True)
    if not row or not token_is_usable(row.status,row.expires_at,cint(row.usage_count),cint(row.max_uses),now_datetime()):
        frappe.throw(_("This guest link is invalid or has expired."),frappe.PermissionError)
    if purpose and row.purpose not in (purpose,"Guest Portal"): frappe.throw(_("This link is not authorized for that action."),frappe.PermissionError)
    if reservation and row.reservation != reservation: frappe.throw(_("This link does not match the reservation."),frappe.PermissionError)
    if consume:
        frappe.db.set_value("Hotel Guest Access Token",row.name,{"usage_count":cint(row.usage_count)+1,"last_used_at":now_datetime(),"last_ip":_client_ip()},update_modified=False)
    return row

def _log(action:str,token=None,reservation=None,customer=None,status="Success",details=None,request_key=None):
    key=make_sync_key("GACT",action,reservation or customer,request_key or secrets.token_hex(6))
    if frappe.db.exists("Hotel Guest Action Log",{"request_key":key}): return
    frappe.get_doc({"doctype":"Hotel Guest Action Log","action":action,"reservation":reservation,"customer":customer,"token_record":getattr(token,"name",None) if token else None,"source_ip":_client_ip(),"user_agent":_user_agent(),"request_key":key,"status":status,"details":details}).insert(ignore_permissions=True)

def _settings_for_slug(slug:str|None):
    filters={"enabled":1,"public_booking_enabled":1}
    if slug: filters["public_slug"]=slug
    name=frappe.db.get_value("Hotel Property",filters,"name")
    if not name: frappe.throw(_("The requested property is not available for online booking."))
    return frappe.get_doc("Hotel Property",name)

def _public_enabled():
    if not cint(frappe.db.get_single_value("Hotel PMS Settings","enable_public_booking")): frappe.throw(_("Online booking is not currently available."))

def _available_rooms(property_name,room_type,arrival,departure):
    # Physical conflicts and active group room blocks share one availability model.
    # The final Reservation validation repeats this under database locks.
    from hotel_pms.hotel_pms.doctype.hotel_group_booking.hotel_group_booking import get_available_room_type_capacity

    rooms=frappe.get_all("Hotel Room",filters={"property":property_name,"room_type":room_type,"enabled":1,"operational_status":("not in",["Out of Order","Out of Service"])},fields=["name","room_number","room_type"],order_by="room_number asc")
    conflicts=set(frappe.db.sql_list("""select distinct rr.room from `tabHotel Reservation` r inner join `tabHotel Reservation Room` rr on rr.parent=r.name where r.property=%(property)s and r.docstatus < 2 and r.status in ('Tentative','Confirmed','Checked In') and r.arrival_date < %(departure)s and r.departure_date > %(arrival)s""",{"property":property_name,"arrival":getdate(arrival),"departure":getdate(departure)}))
    physically_free=[r for r in rooms if r.name not in conflicts]
    sellable=max(cint(get_available_room_type_capacity(property_name,room_type,getdate(arrival),getdate(departure))),0)
    return physically_free[:sellable]

def _validate_public_dates(property_doc,arrival,departure):
    arrival=getdate(arrival); departure=getdate(departure)
    if departure<=arrival or arrival<getdate(): frappe.throw(_("Choose valid future stay dates."))
    horizon=cint(frappe.db.get_single_value("Hotel PMS Settings","public_booking_horizon_days") or 365)
    if arrival>add_days(getdate(),horizon): frappe.throw(_("Arrival is outside the online booking horizon."))
    return arrival,departure

@frappe.whitelist(allow_guest=True)
def get_public_booking_context(property_slug:str|None=None)->dict:
    _rate_limit("context",60,60); _public_enabled(); prop=_settings_for_slug(property_slug)
    gallery=[{"image":r.image,"caption":_plain(r.caption)} for r in prop.public_gallery if r.enabled and r.image]
    return {"property":{"name":prop.name,"slug":prop.public_slug,"public_name":prop.public_name or prop.property_name,"tagline":_plain(prop.public_tagline),"description":_plain(prop.public_description),"address":_plain(prop.address),"contact_email":prop.public_contact_email,"contact_phone":prop.public_contact_phone,"map_url":prop.public_map_url,"policies":_plain(prop.public_policies),"faq":_plain(prop.public_faq),"terms":_plain(prop.public_terms),"privacy_notice":_plain(prop.public_privacy_notice),"hero_image":prop.public_hero_image,"meta_title":prop.public_meta_title or prop.public_name or prop.property_name,"meta_description":_plain(prop.public_meta_description or prop.public_description)[:300],"check_in_time":str(prop.check_in_time or ""),"check_out_time":str(prop.check_out_time or ""),"gallery":gallery}}

@frappe.whitelist(allow_guest=True)
def search_public_availability(property_slug:str,arrival_date:str,departure_date:str,adults:int=2,children:int=0,voucher_code:str|None=None)->dict:
    _rate_limit("search",45,60); _public_enabled(); prop=_settings_for_slug(property_slug); arrival,departure=_validate_public_dates(prop,arrival_date,departure_date)
    from hotel_pms.revenue import _quote_stay_core
    rows=[]
    room_types=frappe.get_all("Hotel Room Type",filters={"property":prop.name,"enabled":1,"public_enabled":1},fields=["name","room_type_name","max_adults","max_children","public_title","public_description","public_image","public_amenities","public_rate_plan","public_display_order"],order_by="public_display_order asc, room_type_name asc")
    for rt in room_types:
        if cint(adults)>cint(rt.max_adults) or cint(children)>cint(rt.max_children): continue
        available=_available_rooms(prop.name,rt.name,arrival,departure)
        if not available or not rt.public_rate_plan: continue
        try: quote=_quote_stay_core(property=prop.name,room_type=rt.name,rate_plan=rt.public_rate_plan,arrival_date=str(arrival),departure_date=str(departure),adults=adults,children=children,voucher_code=voucher_code)
        except Exception: continue
        rows.append({"room_type":rt.name,"title":rt.public_title or rt.room_type_name,"description":rt.public_description,"image":rt.public_image,"amenities":[x.strip() for x in (rt.public_amenities or "").splitlines() if x.strip()],"max_adults":rt.max_adults,"max_children":rt.max_children,"available_rooms":len(available),"rate_plan":rt.public_rate_plan,"quote":quote})
    return {"property":prop.name,"property_slug":prop.public_slug,"arrival_date":str(arrival),"departure_date":str(departure),"rooms":rows}

def _default_tree_leaf(doctype,preferred=None):
    if preferred and frappe.db.exists(doctype,preferred): return preferred
    is_group_field="is_group"
    row=frappe.db.get_value(doctype,{is_group_field:0},"name",order_by="lft asc")
    if not row: frappe.throw(_("Configure at least one non-group {0} before accepting public bookings.").format(doctype))
    return row

def _find_contact(email,phone):
    if email:
        name=frappe.db.sql("select parent from `tabContact Email` where lower(email_id)=%s order by is_primary desc, creation asc limit 1",email,as_dict=False)
        if name:return name[0][0]
    if phone:
        candidates=frappe.db.sql("select parent, phone from `tabContact Phone` order by is_primary_phone desc, creation asc",as_dict=True)
        for row in candidates:
            if normalize_phone(row.phone)==phone:return row.parent
    return None

def _customer_from_contact(contact):
    return frappe.db.get_value("Dynamic Link",{"parenttype":"Contact","parent":contact,"link_doctype":"Customer"},"link_name",order_by="creation asc")

def resolve_or_create_guest(full_name:str,email:str|None,phone:str|None)->dict:
    email=normalize_email(email); phone=normalize_phone(phone)
    contact=_find_contact(email,phone); customer=_customer_from_contact(contact) if contact else None
    if not customer:
        customer=frappe.get_doc({"doctype":"Customer","customer_name":full_name.strip(),"customer_type":"Individual","customer_group":_default_tree_leaf("Customer Group",frappe.db.get_single_value("Selling Settings","customer_group")),"territory":_default_tree_leaf("Territory",frappe.db.get_single_value("Selling Settings","territory"))}).insert(ignore_permissions=True).name
    if not contact:
        c=frappe.get_doc({"doctype":"Contact","first_name":full_name.strip(),"links":[{"link_doctype":"Customer","link_name":customer}]})
        if email:c.append("email_ids",{"email_id":email,"is_primary":1})
        if phone:c.append("phone_nos",{"phone":phone,"is_primary_phone":1})
        c.insert(ignore_permissions=True); contact=c.name
    profile=ensure_guest_profile(customer,contact)
    return {"customer":customer,"contact":contact,"profile":profile}

def ensure_guest_profile(customer:str|None,contact:str|None=None)->str|None:
    if not customer:return None
    existing=frappe.db.get_value("Hotel Guest Profile",{"customer":customer},"name")
    if existing:return existing
    retention=add_days(getdate(),cint(frappe.db.get_single_value("Hotel PMS Settings","privacy_retention_days") or 1825))
    try:return frappe.get_doc({"doctype":"Hotel Guest Profile","customer":customer,"primary_contact":contact,"retention_until":retention}).insert(ignore_permissions=True).name
    except DuplicateEntryError:return frappe.db.get_value("Hotel Guest Profile",{"customer":customer},"name")

def active_blacklist(profile:str|None):
    if not profile:return None
    today=getdate()
    rows=frappe.get_all("Hotel Guest Blacklist",filters={"guest_profile":profile,"status":"Active"},fields=["name","restriction_level","valid_from","valid_until"],order_by="creation desc")
    for row in rows:
        if row.valid_from and getdate(row.valid_from)>today:continue
        if row.valid_until and getdate(row.valid_until)<today:continue
        return row
    return None

@frappe.whitelist(allow_guest=True,methods=["POST"])
def create_public_booking(payload)->dict:
    _rate_limit("book",8,300); _public_enabled(); data=_payload(payload)
    required=["property_slug","room_type","arrival_date","departure_date","adults","guest_name","email","request_key"]
    for name in required:
        if not data.get(name): frappe.throw(_("Missing required field: {0}").format(name))
    if data.get("company_website"): frappe.throw(_("The booking could not be accepted."))
    if not cint(data.get("accept_terms")) or not cint(data.get("accept_privacy")): frappe.throw(_("Hotel terms and privacy notice must be accepted."))
    prop=_settings_for_slug(data["property_slug"]); arrival,departure=_validate_public_dates(prop,data["arrival_date"],data["departure_date"])
    rt=frappe.get_doc("Hotel Room Type",data["room_type"])
    if rt.property!=prop.name or not rt.enabled or not rt.public_enabled or not rt.public_rate_plan: frappe.throw(_("Selected room type is not available online."))
    qty=max(1,min(cint(data.get("quantity") or 1),cint(frappe.db.get_single_value("Hotel PMS Settings","public_booking_max_rooms") or 5)))
    available=_available_rooms(prop.name,rt.name,arrival,departure)
    if len(available)<qty: frappe.throw(_("The requested room quantity is no longer available."))
    guest=resolve_or_create_guest(data["guest_name"],data.get("email"),data.get("phone")); restriction=active_blacklist(guest["profile"])
    if restriction and blacklist_blocks(restriction.restriction_level,"Online"):
        _log("Public Booking",customer=guest["customer"],status="Rejected",details="Restricted guest profile",request_key=data["request_key"])
        frappe.throw(_("This booking cannot be completed online. Please contact the hotel."))
    from hotel_pms.revenue import _quote_stay_core
    quote=_quote_stay_core(property=prop.name,room_type=rt.name,rate_plan=rt.public_rate_plan,arrival_date=str(arrival),departure_date=str(departure),adults=cint(data["adults"]),children=cint(data.get("children") or 0),customer=guest["customer"],voucher_code=data.get("voucher_code"))
    public_key=make_sync_key("PUBLICBOOK",prop.name,data["request_key"])
    existing=frappe.db.get_value("Hotel Reservation",{"idempotency_key":public_key},"name")
    if existing:
        token=issue_guest_token(reservation=existing,customer=guest["customer"],purpose="Guest Portal",request_key=f"portal-retry:{existing}:{secrets.token_hex(6)}")
        return {"reservation":existing,"already_created":True,"portal_token":token.get("raw_token")}
    nights=max((departure-arrival).days,1); rows=[]
    for room in available[:qty]: rows.append({"room_type":rt.name,"room":room.name,"rate_plan":rt.public_rate_plan,"nightly_rate":flt(quote["advertised_total"])/nights,"adults":cint(data["adults"]),"children":cint(data.get("children") or 0)})
    status=frappe.db.get_single_value("Hotel PMS Settings","public_booking_default_status") or "Confirmed"
    deposit_percent=max(min(flt(frappe.db.get_single_value("Hotel PMS Settings","public_booking_deposit_percent") or 0),100),0); required_deposit=flt(quote["grand_total"])*qty*deposit_percent/100
    doc=frappe.get_doc({"doctype":"Hotel Reservation","property":prop.name,"status":status,"guest":guest["customer"],"guest_contact":guest["contact"],"communication_contact":guest["contact"],"billing_customer":guest["customer"],"guest_profile":guest["profile"],"source":"Website","source_reference":data.get("source_reference"),"idempotency_key":public_key,"public_booking_reference":public_key[-16:],"arrival_date":arrival,"departure_date":departure,"arrival_time":data.get("arrival_time"),"adults":cint(data["adults"])*qty,"children":cint(data.get("children") or 0)*qty,"voucher_code":data.get("voucher_code"),"required_deposit":required_deposit,"rooms":rows,"notes":data.get("notes")})
    doc.flags.ignore_permissions=True; doc.insert(ignore_permissions=True); doc.submit()
    for typ in ("Hotel Terms","Privacy Notice"):
        _record_consent(guest["profile"],guest["customer"],doc.name,typ,True,data["request_key"])
    token=issue_guest_token(reservation=doc.name,customer=guest["customer"],purpose="Guest Portal",request_key=f"portal:{doc.name}")
    _log("Public Booking",token=frappe.get_doc("Hotel Guest Access Token",token["token_record"]),reservation=doc.name,customer=guest["customer"],request_key=data["request_key"])
    if cint(frappe.db.get_single_value("Hotel PMS Settings","send_public_booking_email")) and data.get("email") and token.get("raw_token"):
        _send_booking_email(doc,data["email"],token["raw_token"])
    return {"reservation":doc.name,"status":doc.status,"portal_token":token.get("raw_token"),"grand_total":flt(doc.quoted_grand_total),"required_deposit":flt(doc.required_deposit),"already_created":False}

def _record_consent(profile,customer,reservation,consent_type,granted,request_key):
    key=make_sync_key("CONSENT",profile,consent_type,request_key)
    if frappe.db.exists("Hotel Guest Consent",{"idempotency_key":key}):return
    frappe.get_doc({"doctype":"Hotel Guest Consent","guest_profile":profile,"customer":customer,"reservation":reservation,"consent_type":consent_type,"status":"Granted" if granted else "Revoked","captured_via":"Guest Portal","source_ip":_client_ip(),"user_agent":_user_agent(),"idempotency_key":key}).insert(ignore_permissions=True)
    if consent_type.startswith("Marketing") or consent_type=="Privacy Notice":
        frappe.db.set_value("Hotel Guest Profile",profile,{"marketing_consent":1 if granted and consent_type.startswith("Marketing") else frappe.db.get_value("Hotel Guest Profile",profile,"marketing_consent"),"last_consent_at":now_datetime()},update_modified=False)

def _send_booking_email(reservation,email,raw_token):
    portal=frappe.utils.get_url(f"/hotel-guest#token={raw_token}")
    frappe.sendmail(recipients=[email],subject=_("Booking confirmation {0}").format(reservation.name),message=_("Your reservation {0} is confirmed. Manage it securely here: {1}").format(reservation.name,portal),now=False)

@frappe.whitelist(allow_guest=True,methods=["POST"])
def get_guest_portal(raw_token:str)->dict:
    _rate_limit("portal",90,60); token=validate_guest_token(raw_token,purpose="Guest Portal",consume=True); reservation=frappe.get_doc("Hotel Reservation",token.reservation)
    folio=reservation.folio; charges=[]; invoices=[]
    if folio:
        charges=frappe.get_all("Hotel Folio Charge",filters={"parent":folio,"voided":0},fields=["posting_date","description","qty","rate","amount","is_already_invoiced"],order_by="posting_date asc, idx asc")
        invoices=frappe.get_all("Sales Invoice",filters={"custom_hotel_reservation":reservation.name,"docstatus":1},fields=["name","posting_date","grand_total","outstanding_amount","status"],order_by="posting_date desc")
    cancellation_preview=None
    if reservation.status in ("Tentative","Confirmed") and cint(frappe.db.get_single_value("Hotel PMS Settings","enable_guest_cancellation")):
        cancellation_preview=_guest_cancellation_preview(reservation)
    registration=frappe.db.get_value("Hotel Guest Registration",{"reservation":reservation.name},["name","status"],as_dict=True)
    cancellation=None
    if reservation.cancellation_document:
        cancellation=frappe.db.get_value("Hotel Cancellation",reservation.cancellation_document,["name","transaction_type","transaction_date","final_fee","refund_due","status"],as_dict=True)
    privacy_requests=frappe.get_all("Hotel Guest Privacy Request",filters={"customer":reservation.guest},fields=["name","request_type","status","requested_at","eligible_after"],order_by="creation desc",limit=20)
    return {"reservation":{"name":reservation.name,"status":reservation.status,"property":reservation.property,"arrival_date":str(reservation.arrival_date),"departure_date":str(reservation.departure_date),"adults":reservation.adults,"children":reservation.children,"quoted_grand_total":reservation.quoted_grand_total,"required_deposit":reservation.required_deposit,"deposit_received":reservation.deposit_received,"rooms":[{"room_type":r.room_type,"rate_plan":r.rate_plan} for r in reservation.rooms]},"charges":charges,"invoices":invoices,"registration":registration,"cancellation":cancellation,"cancellation_preview":cancellation_preview,"privacy_requests":privacy_requests,"features":{"self_checkin":bool(cint(frappe.db.get_single_value("Hotel PMS Settings","enable_guest_self_checkin"))),"cancellation":bool(cint(frappe.db.get_single_value("Hotel PMS Settings","enable_guest_cancellation")))}}

def _guest_cancellation_preview(reservation):
    from hotel_pms.front_desk import _policy_for_reservation, get_deposit_summary
    from hotel_pms.front_desk_rules import quote_cancellation
    policy=_policy_for_reservation(reservation); rates=[r.nightly_rate for r in reservation.rooms]; deposit=get_deposit_summary(reservation.name)
    q=quote_cancellation(arrival=getdate(reservation.arrival_date),departure=getdate(reservation.departure_date),nightly_rates=rates,reference_date=getdate(),free_cancellation_days=policy.free_cancellation_days if policy else 0,fee_type=policy.fee_type if policy else "None",fee_value=policy.fee_value if policy else 0,deposit_received=deposit["net_deposit"])
    return {"fee_amount":float(q.fee_amount),"refundable_amount":float(q.refundable_amount),"free_cancellation_applies":q.free_cancellation_applies,"days_before_arrival":q.days_before_arrival}

@frappe.whitelist(allow_guest=True,methods=["POST"])
def guest_cancel_reservation(raw_token:str,reason:str,request_key:str)->dict:
    _rate_limit("cancel",8,300); token=validate_guest_token(raw_token,purpose="Cancellation",consume=True); reservation=frappe.get_doc("Hotel Reservation",token.reservation)
    if not cint(frappe.db.get_single_value("Hotel PMS Settings","enable_guest_cancellation")): frappe.throw(_("Guest cancellation is disabled."))
    from hotel_pms.front_desk import process_cancellation_internal
    result=process_cancellation_internal(reservation.name,reason,request_key,transaction_type="Cancellation",waive_fee=0,guest_authorized=True)
    _log("Guest Cancellation",token=token,reservation=reservation.name,customer=reservation.guest,request_key=request_key)
    return result

@frappe.whitelist(allow_guest=True,methods=["POST"])
def submit_self_checkin(raw_token:str,payload)->dict:
    _rate_limit("checkin",12,300); token=validate_guest_token(raw_token,purpose="Self Check-in",consume=True)
    if not cint(frappe.db.get_single_value("Hotel PMS Settings","enable_guest_self_checkin")): frappe.throw(_("Guest self check-in is disabled."))
    data=_payload(payload); reservation=frappe.get_doc("Hotel Reservation",token.reservation)
    if reservation.status not in ("Tentative","Confirmed"): frappe.throw(_("This reservation cannot accept self check-in details."))
    name=frappe.db.get_value("Hotel Guest Registration",{"reservation":reservation.name},"name")
    doc=frappe.get_doc("Hotel Guest Registration",name) if name else frappe.new_doc("Hotel Guest Registration")
    if not name:
        doc.update({"reservation":reservation.name,"property":reservation.property,"guest":reservation.guest,"guest_contact":reservation.guest_contact,"arrival_date":reservation.arrival_date,"departure_date":reservation.departure_date,"id_retention_mode":"Do Not Upload"})
    doc.vehicle_number=data.get("vehicle_number"); doc.primary_id_type=data.get("primary_id_type"); doc.primary_id_number=data.get("primary_id_number"); doc.signature_name=data.get("signature_name")
    doc.terms_accepted=cint(data.get("terms_accepted")); doc.privacy_consent=cint(data.get("privacy_consent"))
    if not doc.terms_accepted or not doc.privacy_consent: frappe.throw(_("Hotel terms and privacy notice must be accepted."))
    doc.status="Completed"
    doc.set("occupants",[])
    occupants=data.get("occupants") or []
    for idx,row in enumerate(occupants):
        if not row.get("full_name"):continue
        doc.append("occupants",{"full_name":row.get("full_name"),"is_primary_guest":1 if idx==0 else 0,"nationality":row.get("nationality"),"id_type":row.get("id_type"),"id_number":row.get("id_number")})
    if not doc.occupants: frappe.throw(_("Add at least one occupant."))
    doc.save(ignore_permissions=True)
    frappe.db.set_value("Hotel Reservation",reservation.name,"registration",doc.name,update_modified=False)
    _record_consent(token.guest_profile,reservation.guest,reservation.name,"Hotel Terms",True,data.get("request_key") or request_key_fallback(reservation.name,"terms"))
    _record_consent(token.guest_profile,reservation.guest,reservation.name,"Privacy Notice",True,data.get("request_key") or request_key_fallback(reservation.name,"privacy"))
    _log("Self Check-in",token=token,reservation=reservation.name,customer=reservation.guest,request_key=data.get("request_key"))
    return {"registration":doc.name,"status":doc.status}

def request_key_fallback(reservation,suffix):return f"{reservation}:{suffix}"

@frappe.whitelist(allow_guest=True,methods=["POST"])
def guest_create_payment_request(raw_token:str,request_key:str,payment_gateway_account:str|None=None)->dict:
    _rate_limit("payment",8,300); token=validate_guest_token(raw_token,purpose="Payment",consume=True); reservation=frappe.get_doc("Hotel Reservation",token.reservation)
    invoices=frappe.get_all("Sales Invoice",filters={"custom_hotel_reservation":reservation.name,"docstatus":1,"outstanding_amount":(">",0)},fields=["name","outstanding_amount"],order_by="posting_date asc")
    if invoices:
        # Internal guest-safe use: payment target is strictly derived from token reservation.
        return _create_payment_request_from_invoice(invoices[0].name,reservation,token,payment_gateway_account)
    if flt(reservation.required_deposit)<=flt(reservation.deposit_received): frappe.throw(_("No online payment is currently due."))
    sales_order=_ensure_deposit_sales_order(reservation)
    return _make_payment_request("Sales Order",sales_order.name,reservation,token,payment_gateway_account)

def _ensure_deposit_sales_order(reservation):
    item=frappe.db.get_single_value("Hotel PMS Settings","default_booking_deposit_item")
    if not item: frappe.throw(_("Booking Deposit Item is not configured."))
    property_doc=frappe.get_doc("Hotel Property",reservation.property); due=max(flt(reservation.required_deposit)-flt(reservation.deposit_received),0)
    key=make_sync_key("SO","BOOKING-DEPOSIT",reservation.name)
    def build():
        so=frappe.new_doc("Sales Order"); so.company=property_doc.company; so.customer=reservation.billing_customer or reservation.guest; so.transaction_date=getdate(); so.delivery_date=getdate(reservation.arrival_date); so.custom_hotel_reservation=reservation.name
        so.append("items",{"item_code":item,"description":f"Reservation deposit {reservation.name}","qty":1,"rate":due,"delivery_date":getdate(reservation.arrival_date),"cost_center":reservation.cost_center or property_doc.default_cost_center})
        return so
    so,already=create_document_once(base_key=key,operation="Create Booking Deposit Sales Order",source_doctype=reservation.doctype,source_name=reservation.name,target_doctype="Sales Order",build_document=build,payload={"reservation":reservation.name,"amount":due},ignore_permissions=True)
    if so.docstatus==0: so.flags.ignore_permissions=True; so.submit()
    return so

def _create_payment_request_from_invoice(invoice_name,reservation,token,gateway):
    return _make_payment_request("Sales Invoice",invoice_name,reservation,token,gateway)

def _make_payment_request(dt,dn,reservation,token,gateway):
    from erpnext.accounts.doctype.payment_request.payment_request import make_payment_request
    gateway=gateway or frappe.db.get_value("Hotel Property",reservation.property,"default_payment_gateway_account")
    key=make_sync_key("PAYREQ","GUEST",dt,dn,gateway or "DEFAULT")
    existing=frappe.db.get_value("Payment Request",{"custom_hotel_sync_key":key,"docstatus":("<",2)},["name","payment_url"],as_dict=True)
    if existing:return {"payment_request":existing.name,"payment_url":existing.payment_url,"already_created":True}
    contact_email=frappe.db.get_value("Contact Email",{"parent":reservation.communication_contact,"is_primary":1},"email_id") if reservation.communication_contact else None
    ref=frappe.get_doc(dt,dn)
    pr=make_payment_request(dt=dt,dn=dn,recipient_id=contact_email or ref.owner,payment_gateway_account=gateway,submit_doc=0,return_doc=1,mute_email=1,party_type="Customer",party=reservation.billing_customer or reservation.guest,party_name=reservation.billing_customer or reservation.guest,mode_of_payment=None,make_sales_invoice=0)
    if isinstance(pr,dict):pr=frappe.get_doc(pr)
    if pr.get("__unsaved"):pr.insert(ignore_permissions=True)
    pr.db_set({"custom_hotel_sync_key":key,"custom_hotel_guest_token":token.name})
    if pr.docstatus==0: pr.flags.mute_email=True; pr.flags.ignore_permissions=True; pr.submit()
    _log("Payment Request",token=token,reservation=reservation.name,customer=reservation.guest,request_key=key)
    return {"payment_request":pr.name,"payment_url":pr.payment_url,"already_created":False}

@frappe.whitelist()
def get_guest_profile_360(customer:str)->dict:
    frappe.only_for(["System Manager","Hotel Manager","Front Desk","Hotel Sales","Credit Manager"])
    profile_name=ensure_guest_profile(customer); profile=frappe.get_doc("Hotel Guest Profile",profile_name)
    stays=frappe.get_all("Hotel Reservation",filters={"guest":customer},fields=["name","property","status","arrival_date","departure_date","quoted_grand_total","folio"],order_by="arrival_date desc",limit=100)
    completed=[s for s in stays if s.status=="Checked Out"]; nights=sum(max((getdate(s.departure_date)-getdate(s.arrival_date)).days,0) for s in completed); revenue=sum(flt(s.quoted_grand_total) for s in completed)
    today=getdate(); past=[s for s in completed if getdate(s.departure_date)<=today]; future=[s for s in stays if s.status in ("Tentative","Confirmed") and getdate(s.arrival_date)>=today]
    values={"lifetime_stays":len(completed),"lifetime_room_nights":nights,"lifetime_revenue":revenue,"last_stay_date":max([getdate(s.departure_date) for s in past],default=None),"next_stay_date":min([getdate(s.arrival_date) for s in future],default=None),"last_refreshed_at":now_datetime()}
    frappe.db.set_value("Hotel Guest Profile",profile.name,values,update_modified=False); profile.reload()
    contacts=frappe.db.sql("""select c.name,c.first_name,c.last_name from `tabContact` c inner join `tabDynamic Link` dl on dl.parent=c.name and dl.parenttype='Contact' where dl.link_doctype='Customer' and dl.link_name=%s""",customer,as_dict=True)
    lost=frappe.get_all("Hotel Lost and Found",filters={"reservation":("in",[s.name for s in stays] or [""])},fields=["name","status","item_category","description","found_at"],order_by="found_at desc",limit=20)
    complaints=frappe.get_all("Hotel Maintenance Ticket",filters={"reservation":("in",[s.name for s in stays] or [""]),"source":"Guest Complaint"},fields=["name","status","priority","problem_description","reported_at"],order_by="reported_at desc",limit=20)
    consents=frappe.get_all("Hotel Guest Consent",filters={"customer":customer},fields=["consent_type","status","captured_at","revoked_at"],order_by="creation desc",limit=50)
    return {"profile":profile.as_dict(),"contacts":contacts,"stays":stays,"lost_and_found":lost,"guest_complaints":complaints,"consents":consents,"blacklist":active_blacklist(profile.name)}

@frappe.whitelist()
def find_guest_duplicates(customer:str)->list[dict]:
    frappe.only_for(["System Manager","Hotel Manager","Front Desk"]); contacts=frappe.db.sql("""select c.name,ce.email_id,cp.phone from `tabContact` c inner join `tabDynamic Link` dl on dl.parent=c.name and dl.parenttype='Contact' left join `tabContact Email` ce on ce.parent=c.name left join `tabContact Phone` cp on cp.parent=c.name where dl.link_doctype='Customer' and dl.link_name=%s""",customer,as_dict=True)
    emails={normalize_email(r.email_id) for r in contacts if r.email_id}; phones={normalize_phone(r.phone) for r in contacts if r.phone}; candidates={}
    allrows=frappe.db.sql("""select dl.link_name customer,c.name contact,ce.email_id,cp.phone from `tabContact` c inner join `tabDynamic Link` dl on dl.parent=c.name and dl.parenttype='Contact' left join `tabContact Email` ce on ce.parent=c.name left join `tabContact Phone` cp on cp.parent=c.name where dl.link_doctype='Customer' and dl.link_name!=%s""",customer,as_dict=True)
    for r in allrows:
        reasons=[]
        if normalize_email(r.email_id) in emails and r.email_id:reasons.append("Email")
        if normalize_phone(r.phone) in phones and r.phone:reasons.append("Phone")
        if reasons:candidates.setdefault(r.customer,set()).update(reasons)
    return [{"customer":k,"customer_name":frappe.db.get_value("Customer",k,"customer_name"),"match_reason":", ".join(sorted(v))} for k,v in candidates.items()]

@frappe.whitelist()
def execute_guest_merge(merge_request:str)->dict:
    frappe.only_for(["System Manager","Hotel Manager"]); doc=frappe.get_doc("Hotel Guest Merge Request",merge_request); doc.check_permission("write")
    if doc.status not in ("Approved","Draft"): frappe.throw(_("Merge request is not eligible."))
    if doc.primary_customer==doc.duplicate_customer: frappe.throw(_("Primary and duplicate customer cannot be the same."))
    key=doc.idempotency_key or make_sync_key("GMERGE",doc.primary_customer,doc.duplicate_customer)
    existing=frappe.db.get_value("Hotel Guest Merge Request",{"idempotency_key":key,"status":"Completed"},"name")
    if existing:return {"merge_request":existing,"already_completed":True}
    doc.db_set({"status":"Approved","approved_by":frappe.session.user,"approved_at":now_datetime(),"idempotency_key":key})
    primary_profile=ensure_guest_profile(doc.primary_customer); duplicate_profile=frappe.db.get_value("Hotel Guest Profile",{"customer":doc.duplicate_customer},"name")
    if duplicate_profile:
        for dt in ("Hotel Guest Consent","Hotel Guest Blacklist","Hotel Guest Privacy Request","Hotel Guest Access Token"):
            if frappe.get_meta(dt).has_field("guest_profile"):
                for row_name in frappe.get_all(dt, filters={"guest_profile": duplicate_profile}, pluck="name"):
                    frappe.db.set_value(dt, row_name, "guest_profile", primary_profile, update_modified=False)
        frappe.db.set_value("Customer", doc.duplicate_customer, "custom_hotel_guest_profile", None, update_modified=False)
        frappe.delete_doc("Hotel Guest Profile",duplicate_profile,ignore_permissions=True)
    frappe.rename_doc("Customer",doc.duplicate_customer,doc.primary_customer,merge=True)
    doc.db_set({"status":"Completed","completed_at":now_datetime()})
    return {"merge_request":doc.name,"primary_customer":doc.primary_customer,"already_completed":False}

@frappe.whitelist(allow_guest=True,methods=["POST"])
def submit_privacy_request(raw_token:str,request_type:str,details:str|None=None,request_key:str|None=None)->dict:
    _rate_limit("privacy",5,600); token=validate_guest_token(raw_token,purpose="Privacy Request",consume=True); key=make_sync_key("PRIVREQ",token.customer,request_type,request_key)
    existing=frappe.db.get_value("Hotel Guest Privacy Request",{"idempotency_key":key},"name")
    if existing:return {"privacy_request":existing,"already_created":True}
    doc=frappe.get_doc({"doctype":"Hotel Guest Privacy Request","guest_profile":token.guest_profile or ensure_guest_profile(token.customer),"customer":token.customer,"request_type":request_type,"request_details":details,"portal_token":token.name,"idempotency_key":key}).insert(ignore_permissions=True)
    _log("Privacy Request",token=token,customer=token.customer,request_key=key)
    return {"privacy_request":doc.name,"status":doc.status,"eligible_after":doc.eligible_after,"already_created":False}

@frappe.whitelist()
def process_privacy_request(request_name:str,completion_notes:str|None=None)->dict:
    frappe.only_for(["System Manager","Hotel Manager","Accounts Manager"]); doc=frappe.get_doc("Hotel Guest Privacy Request",request_name); doc.check_permission("write")
    if doc.status not in ("Approved","Cooling Period"): frappe.throw(_("Privacy request must be approved before processing."))
    if getdate()<getdate(doc.eligible_after): frappe.throw(_("Cooling period has not ended."))
    generated_note=None
    if doc.request_type=="Marketing Opt-out":
        frappe.db.set_value("Hotel Guest Profile",doc.guest_profile,"marketing_consent",0)
        generated_note="Marketing consent revoked."
    elif doc.request_type=="Anonymization":
        active=frappe.db.count("Hotel Reservation",{"guest":doc.customer,"status":("in",["Tentative","Confirmed","Checked In"])})
        outstanding=frappe.db.sql("select coalesce(sum(outstanding_amount),0) from `tabSales Invoice` where customer=%s and docstatus=1",doc.customer)[0][0]
        hold=frappe.db.get_value("Hotel Guest Profile",doc.guest_profile,"privacy_status")=="Retention Hold"
        if not can_anonymize(active,outstanding,hold): frappe.throw(_("Guest cannot be anonymized while active stays, outstanding receivables, or a retention hold exist."))
        alias=f"ANON-{hashlib.sha256(doc.customer.encode()).hexdigest()[:12].upper()}"
        contacts=[row[0] for row in frappe.db.sql("""select c.name from `tabContact` c inner join `tabDynamic Link` dl on dl.parent=c.name and dl.parenttype='Contact' where dl.link_doctype='Customer' and dl.link_name=%s""",doc.customer)]
        for contact_name in contacts:
            contact=frappe.get_doc("Contact",contact_name); contact.first_name=alias; contact.last_name=None; contact.set("email_ids",[]); contact.set("phone_nos",[]); contact.save(ignore_permissions=True)
        customer_doc=frappe.get_doc("Customer",doc.customer)
        original_customer_name=customer_doc.customer_name or ""
        customer_doc.customer_name=alias
        customer_doc.save(ignore_permissions=True)
        current_customer=doc.customer
        if original_customer_name and original_customer_name.lower() in current_customer.lower() and not frappe.db.exists("Customer",alias):
            current_customer=frappe.rename_doc("Customer",current_customer,alias,merge=False)
            doc.db_set("customer",current_customer)
        frappe.db.set_value("Hotel Guest Profile",doc.guest_profile,{"status":"Anonymized","privacy_status":"Anonymized","preferred_name":None,"date_of_birth":None,"dietary_notes":None,"allergies":None,"accessibility_notes":None,"service_notes":None,"marketing_consent":0},update_modified=False)
        generated_note="Personal profile and contact fields anonymized while accounting documents were retained."
    elif doc.request_type=="Data Access":
        payload=_privacy_export(doc.customer,doc.guest_profile)
        doc.db_set("export_payload",json.dumps(payload,default=str,ensure_ascii=False,indent=2))
        generated_note="Data access export generated."
    elif doc.request_type=="Correction":
        if not completion_notes: frappe.throw(_("Record the corrections made before completing this request."))
        generated_note=completion_notes
    doc.db_set({"status":"Completed","completed_at":now_datetime(),"completion_notes":completion_notes or generated_note or f"Processed by {frappe.session.user}"})
    return {"privacy_request":doc.name,"status":"Completed"}


def _privacy_export(customer:str,profile_name:str)->dict:
    profile=frappe.get_doc("Hotel Guest Profile",profile_name).as_dict()
    for key in ("owner","modified_by","_comments","_assign","_liked_by"): profile.pop(key,None)
    contacts=frappe.db.sql("""select c.name,c.first_name,c.last_name from `tabContact` c inner join `tabDynamic Link` dl on dl.parent=c.name and dl.parenttype='Contact' where dl.link_doctype='Customer' and dl.link_name=%s""",customer,as_dict=True)
    reservations=frappe.get_all("Hotel Reservation",filters={"guest":customer},fields=["name","property","status","arrival_date","departure_date","adults","children","source","quoted_grand_total"],order_by="arrival_date desc")
    consents=frappe.get_all("Hotel Guest Consent",filters={"customer":customer},fields=["consent_type","status","captured_via","captured_at","revoked_at"],order_by="creation desc")
    return {"generated_at":str(now_datetime()),"customer":customer,"profile":profile,"contacts":contacts,"reservations":reservations,"consents":consents}


@frappe.whitelist(allow_guest=True,methods=["POST"])
def get_privacy_request_result(raw_token:str,request_name:str)->dict:
    _rate_limit("privacy-result",12,300); token=validate_guest_token(raw_token,purpose="Privacy Request",consume=True)
    doc=frappe.get_doc("Hotel Guest Privacy Request",request_name)
    if doc.customer!=token.customer: frappe.throw(_("This request does not belong to the guest link."),frappe.PermissionError)
    result={"privacy_request":doc.name,"request_type":doc.request_type,"status":doc.status,"completion_notes":doc.completion_notes}
    if doc.request_type=="Data Access" and doc.status=="Completed" and doc.export_payload:
        result["export"]=json.loads(doc.export_payload)
    return result


def expire_guest_tokens():
    if not cint(frappe.db.get_single_value("Hotel PMS Settings","auto_expire_guest_tokens")):return
    names=frappe.get_all("Hotel Guest Access Token",filters={"status":"Active","expires_at":("<",now_datetime())},pluck="name")
    for name in names: frappe.db.set_value("Hotel Guest Access Token",name,"status","Expired",update_modified=False)

def expire_blacklist_records():
    names=frappe.get_all("Hotel Guest Blacklist",filters={"status":"Active","valid_until":("<",getdate())},pluck="name")
    for name in names:
        doc=frappe.get_doc("Hotel Guest Blacklist",name); doc.status="Expired"; doc.save(ignore_permissions=True)


def validate_reservation_guest_status(reservation) -> None:
    profile = reservation.guest_profile or (ensure_guest_profile(reservation.guest, reservation.guest_contact) if reservation.guest else None)
    if profile and reservation.guest_profile != profile:
        reservation.guest_profile = profile
    restriction = active_blacklist(profile)
    if not restriction:
        return
    if restriction.restriction_level == "Block All":
        roles=set(frappe.get_roles())
        if not reservation.blacklist_override_reason or not ({"System Manager","Hotel Manager"} & roles):
            frappe.throw(_("Guest profile is blocked. A Hotel Manager must record an override reason."))
        reservation.blacklist_override_by=frappe.session.user
    elif restriction.restriction_level in ("Warning","Review"):
        reservation.add_comment("Info", _("Guest profile restriction: {0}").format(restriction.restriction_level)) if not reservation.is_new() else None


@frappe.whitelist()
def issue_portal_link_for_staff(reservation: str, request_key: str) -> dict:
    frappe.only_for(["System Manager","Hotel Manager","Front Desk","Hotel Sales"])
    doc=frappe.get_doc("Hotel Reservation",reservation); doc.check_permission("read")
    return issue_guest_token(reservation=doc.name,customer=doc.guest,purpose="Guest Portal",request_key=request_key)
