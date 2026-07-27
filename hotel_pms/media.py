from __future__ import annotations

import mimetypes

import frappe
from frappe import _
from frappe.utils import cint

PHOTO_FIELDS_BY_DOCTYPE = {
    "Hotel Property": {"public_hero_image"},
    "Hotel Room Type": {"public_image"},
    "Hotel Booking Gallery Image": {"image"},
    "Hotel Housekeeping Task": {"before_photo", "after_photo"},
    "Hotel Maintenance Ticket": {"before_photo", "after_photo"},
    # Future modules can use the same global policy without changing the File hook.
    "Hotel Lost and Found": {"item_photo"},
    "Hotel Lost and Found Custody": {"handover_photo"},
    "Hotel Room Inspection": {"inspection_photo"},
    "Hotel Room Inspection Item": {"photo"},
    "Hotel Housekeeping Checklist Item": {"photo"},
    "Hotel Guest Registration": {"id_file"},
    "Hotel Inspection Finding": {"finding_photo", "resolution_photo"},
    "Hotel SOP Candidate": {"before_photo", "after_photo", "reference_photo"},
}


def photo_uploads_enabled() -> bool:
    """Return the single source of truth for Hotel PMS evidence-photo uploads."""
    return bool(cint(frappe.db.get_single_value("Hotel PMS Settings", "enable_photo_uploads") or 0))


@frappe.whitelist()
def get_photo_policy() -> dict:
    frappe.only_for(["System Manager", "Hotel Manager", "Front Desk", "Housekeeping", "Housekeeping Supervisor", "Engineering", "Engineering Supervisor", "Hotel Sales", "Banquet"])
    enabled = photo_uploads_enabled()
    return {
        "enabled": enabled,
        "message": _("Hotel evidence photo uploads are enabled.")
        if enabled
        else _("Hotel evidence photo uploads are disabled by Hotel PMS Settings."),
    }


def validate_photo_fields(document, fieldnames: set[str] | tuple[str, ...] | list[str]) -> None:
    """Reject new/changed image field values while storage-saving mode is active.

    Existing photos are deliberately preserved. Disabling the feature is not a silent
    delete operation, because deleting evidence merely to save disk space would be a
    particularly inventive way to damage an audit trail.
    """
    if photo_uploads_enabled():
        return

    old_doc = None
    if not document.is_new():
        old_doc = document.get_doc_before_save()

    changed = []
    for fieldname in fieldnames:
        value = document.get(fieldname)
        if not value:
            continue
        old_value = old_doc.get(fieldname) if old_doc else None
        if document.is_new() or value != old_value:
            changed.append(document.meta.get_label(fieldname) or fieldname)

    if changed:
        frappe.throw(
            _("Photo uploads are disabled in Hotel PMS Settings. Remove the new value from: {0}.").format(
                ", ".join(changed)
            )
        )


def _is_hotel_image_upload(doctype: str | None, fieldname: str | None, filename: str | None) -> bool:
    if not doctype or not doctype.startswith("Hotel "):
        return False
    content_type = mimetypes.guess_type(filename or "")[0] or ""
    photo_field = bool(fieldname and ("photo" in fieldname.lower() or fieldname in PHOTO_FIELDS_BY_DOCTYPE.get(doctype, set())))
    return content_type.startswith("image/") or photo_field


def validate_file_upload(file_doc, method=None) -> None:
    """Fallback guard for File records created outside the normal upload endpoint."""
    if photo_uploads_enabled():
        return
    if _is_hotel_image_upload(
        getattr(file_doc, "attached_to_doctype", None),
        getattr(file_doc, "attached_to_field", None),
        getattr(file_doc, "file_name", None),
    ):
        frappe.throw(
            _("Photo uploads are disabled in Hotel PMS Settings to conserve server storage."),
            title=_("Photo Upload Disabled"),
        )


def validate_upload_request() -> None:
    if photo_uploads_enabled():
        return
    doctype = frappe.form_dict.get("doctype")
    fieldname = frappe.form_dict.get("fieldname")
    filename = frappe.form_dict.get("file_name") or frappe.form_dict.get("file_url")
    files = getattr(frappe.local.request, "files", {}) if getattr(frappe.local, "request", None) else {}
    if files and "file" in files:
        filename = files["file"].filename
    if _is_hotel_image_upload(doctype, fieldname, filename):
        frappe.throw(
            _("Photo uploads are disabled in Hotel PMS Settings to conserve server storage."),
            title=_("Photo Upload Disabled"),
        )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def upload_file():
    """Storage-policy wrapper around Frappe's standard upload endpoint."""
    validate_upload_request()
    from frappe.handler import upload_file as frappe_upload_file

    return frappe_upload_file()
