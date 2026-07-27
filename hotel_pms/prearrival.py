from __future__ import annotations

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, strip_html

from hotel_pms.distribution_rules import json_hash, snapshot_answers
from hotel_pms.guest_portal import issue_guest_token, validate_guest_token
from hotel_pms.platform import require_property
from hotel_pms.sync import make_sync_key


def _questions(template) -> list[dict]:
    return [
        {
            "field_key": row.field_key,
            "field_type": row.field_type,
            "label": strip_html(row.label or "").strip(),
            "help_text": strip_html(row.help_text or "").strip(),
            "required": bool(row.required),
            "options": [x.strip() for x in (row.options or "").splitlines() if x.strip()],
        }
        for row in template.questions
    ]


@frappe.whitelist()
def issue_prearrival_form(reservation: str, template: str | None = None, request_key: str | None = None) -> dict:
    frappe.only_for(["System Manager", "Hotel Manager", "Front Desk", "Guest Services"])
    res = frappe.get_doc("Hotel Reservation", reservation)
    require_property(res.property, write=True)
    if res.status not in ("Tentative", "Confirmed"):
        frappe.throw(_("Pre-arrival forms can only be issued before check-in."))
    template = template or frappe.db.get_value(
        "Hotel Prearrival Form Template", {"property": res.property, "enabled": 1}, "name", order_by="creation asc"
    )
    if not template:
        frappe.throw(_("Configure an enabled pre-arrival form template for this property."))
    active = frappe.db.get_value(
        "Hotel Prearrival Form Submission",
        {"reservation": res.name, "template": template, "status": ("in", ["Draft", "Issued"])},
        "name",
        order_by="creation desc",
    )
    if active:
        row = frappe.db.get_value("Hotel Prearrival Form Submission", active, ["status", "token_record"], as_dict=True)
        return {"submission": active, "status": row.status, "raw_token": None, "already_created": True}
    key = make_sync_key("PREFORM", reservation, template, request_key or "default")
    existing = frappe.db.get_value("Hotel Prearrival Form Submission", {"request_key": key}, "name")
    if existing:
        row = frappe.db.get_value("Hotel Prearrival Form Submission", existing, ["status", "token_record"], as_dict=True)
        return {"submission": existing, "status": row.status, "raw_token": None, "already_created": True}
    token = issue_guest_token(
        reservation=res.name,
        customer=res.guest,
        purpose="Pre-arrival Form",
        valid_days=max((getdate(res.arrival_date) - getdate()).days + 2, 2),
        request_key=key,
        max_uses=1,
    )
    doc = frappe.get_doc({
        "doctype": "Hotel Prearrival Form Submission",
        "property": res.property,
        "reservation": res.name,
        "template": template,
        "token_record": token["token_record"],
        "status": "Issued",
        "request_key": key,
        "issued_at": now_datetime(),
    }).insert(ignore_permissions=True)
    frappe.db.set_value("Hotel Reservation", res.name, "prearrival_submission", doc.name, update_modified=False)
    raw = token.get("raw_token")
    return {
        "submission": doc.name,
        "status": doc.status,
        "raw_token": raw,
        "url": frappe.utils.get_url(f"/hotel-prearrival?token={raw}") if raw else None,
        "already_created": False,
    }


@frappe.whitelist(allow_guest=True)
def get_prearrival_form(raw_token: str) -> dict:
    token = validate_guest_token(raw_token, purpose="Pre-arrival Form", consume=False)
    submission_name = frappe.db.get_value(
        "Hotel Prearrival Form Submission", {"token_record": token.name, "reservation": token.reservation}, "name"
    )
    if not submission_name:
        frappe.throw(_("Pre-arrival form not found."), frappe.DoesNotExistError)
    submission = frappe.get_doc("Hotel Prearrival Form Submission", submission_name)
    template = frappe.get_doc("Hotel Prearrival Form Template", submission.template)
    reservation = frappe.get_doc("Hotel Reservation", submission.reservation)
    prop = frappe.get_doc("Hotel Property", submission.property)
    return {
        "submission": submission.name,
        "status": submission.status,
        "property": prop.public_name or prop.property_name,
        "reservation": reservation.name,
        "guest": frappe.db.get_value("Customer", reservation.guest, "customer_name") or reservation.guest,
        "arrival_date": str(reservation.arrival_date),
        "departure_date": str(reservation.departure_date),
        "title": template.title,
        "language": template.language or "id",
        "privacy_notice": strip_html(template.privacy_notice or prop.public_privacy_notice or "").strip(),
        "questions": _questions(template),
        "submitted_at": str(submission.submitted_at or ""),
    }


@frappe.whitelist(allow_guest=True, methods=["POST"])
def submit_prearrival_form(raw_token: str, answers) -> dict:
    token = validate_guest_token(raw_token, purpose="Pre-arrival Form", consume=False)
    submission_name = frappe.db.get_value(
        "Hotel Prearrival Form Submission", {"token_record": token.name, "reservation": token.reservation}, "name"
    )
    if not submission_name:
        frappe.throw(_("Pre-arrival form not found."), frappe.DoesNotExistError)
    # Row lock makes the one-time rule true under concurrency, rather than merely aspirational.
    frappe.db.sql("select name from `tabHotel Prearrival Form Submission` where name=%s for update", submission_name)
    submission = frappe.get_doc("Hotel Prearrival Form Submission", submission_name)
    if submission.status == "Submitted":
        frappe.throw(_("This form has already been submitted."), frappe.ValidationError)
    data = json.loads(answers) if isinstance(answers, str) else (answers or {})
    if not isinstance(data, dict):
        frappe.throw(_("Answers must be a JSON object."))
    template = frappe.get_doc("Hotel Prearrival Form Template", submission.template)
    try:
        snapshot = snapshot_answers(_questions(template), data)
    except ValueError as exc:
        frappe.throw(_(str(exc)))
    # Consume only after validation; invalid attempts do not burn the guest's one useful link.
    validate_guest_token(raw_token, purpose="Pre-arrival Form", reservation=submission.reservation, consume=True)
    encoded = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, default=str)
    ip = ""
    request = getattr(frappe.local, "request", None)
    if request:
        ip = (request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or getattr(request, "remote_addr", ""))
    submission.answers_json = encoded
    submission.answers_hash = json_hash(snapshot)
    submission.source_ip_hash = hashlib.sha256(ip.encode()).hexdigest() if ip else ""
    submission.submitted_at = now_datetime()
    submission.status = "Submitted"
    submission.save(ignore_permissions=True)
    return {"submission": submission.name, "status": submission.status, "submitted_at": submission.submitted_at}


@frappe.whitelist()
def revoke_prearrival_form(submission: str) -> dict:
    frappe.only_for(["System Manager", "Hotel Manager", "Front Desk"])
    doc = frappe.get_doc("Hotel Prearrival Form Submission", submission)
    require_property(doc.property, write=True)
    if doc.status == "Submitted":
        frappe.throw(_("Submitted answers are retained according to the property privacy policy and cannot be revoked through the link workflow."))
    doc.status = "Revoked"
    doc.save(ignore_permissions=True)
    if doc.token_record:
        frappe.db.set_value("Hotel Guest Access Token", doc.token_record, {"status": "Revoked", "revoked_at": now_datetime(), "revoked_by": frappe.session.user}, update_modified=False)
    return {"submission": doc.name, "status": doc.status}
