from __future__ import annotations

import mimetypes

import frappe
from frappe import _
from frappe.utils import cint

PHOTO_FIELDS_BY_DOCTYPE = {
    "Hotel Property": {"public_hero_image"},
    "Hotel Room Type": {"public_image"},
    "Hotel Booking Gallery Image": {"image"},
    "Hotel Outlet Menu Item": {"image"},
    "Hotel Guest Experience": {"image"},
    "Hotel Housekeeping Task": {"before_photo", "after_photo"},
    "Hotel Maintenance Ticket": {"before_photo", "after_photo"},
    # Future modules can use the same global policy without changing the File hook.
    "Hotel Lost and Found": {"item_photo"},
    "Hotel Lost and Found Custody": {"handover_photo"},
    "Hotel Room Inspection": {"inspection_photo"},
    "Hotel Room Inspection Item": {"photo"},
    "Hotel Housekeeping Checklist Item": {"photo"},
    "Hotel Guest Registration": {"id_file", "address_proof_file"},
    "Hotel Inspection Finding": {"finding_photo", "resolution_photo"},
    "Hotel SOP Candidate": {"before_photo", "after_photo", "reference_photo"},
}


def photo_uploads_enabled() -> bool:
    """Return the single source of truth for Hotel PMS evidence-photo uploads."""
    return bool(cint(frappe.db.get_single_value("Hotel PMS Settings", "enable_photo_uploads") or 0))


@frappe.whitelist()
def get_photo_policy() -> dict:
    frappe.only_for(["System Manager", "Hotel Manager", "Front Desk", "Housekeeping", "Housekeeping Supervisor", "Engineering", "Engineering Supervisor", "Hotel Sales", "Banquet", "Restaurant Cashier", "Restaurant Captain", "Kitchen", "Laundry", "Guest Services"])
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


# Guest identity documents use an explicit private, re-encoding pipeline. They never
# create accounting or operational ledger rows.
def _decode_image_payload(image_data: str) -> bytes:
    import base64
    value=(image_data or "").strip()
    if "," in value and value.lower().startswith("data:image/"): value=value.split(",",1)[1]
    try:return base64.b64decode(value,validate=True)
    except Exception:frappe.throw(_("Invalid image payload."))

def sanitize_guest_document(image_data: str) -> tuple[bytes,str]:
    if not photo_uploads_enabled():frappe.throw(_("Photo uploads are disabled in Hotel PMS Settings."))
    from io import BytesIO
    from PIL import Image,ImageOps,UnidentifiedImageError
    max_mb=max(1,min(cint(frappe.db.get_single_value("Hotel PMS Settings","guest_document_max_mb") or 3),10))
    # Base64 is roughly 4/3 of the decoded size. Reject obviously oversized
    # payloads before allocating decoded bytes.
    if len(image_data or "") > int(max_mb * 1024 * 1024 * 1.5) + 4096:
        frappe.throw(_("Guest document exceeds the configured size limit."))
    raw=_decode_image_payload(image_data)
    if len(raw)>max_mb*1024*1024:frappe.throw(_("Guest document exceeds the configured size limit."))
    try:
        im=Image.open(BytesIO(raw))
        source_format=im.format
        if source_format not in ("JPEG","PNG","WEBP"):
            frappe.throw(_("Unsupported guest document image format."))
        max_pixels=25_000_000
        if (im.width or 0) * (im.height or 0) > max_pixels:
            frappe.throw(_("Guest document dimensions are too large."))
        im=ImageOps.exif_transpose(im); im.load()
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError):frappe.throw(_("Guest document must be a valid JPEG, PNG, or WebP image."))
    max_dim=max(800,min(cint(frappe.db.get_single_value("Hotel PMS Settings","guest_document_max_dimension") or 2200),5000))
    im.thumbnail((max_dim,max_dim))
    if im.mode not in ("RGB","L"):im=im.convert("RGB")
    elif im.mode=="L":im=im.convert("RGB")
    output=BytesIO(); im.save(output,format="JPEG",quality=88,optimize=True)
    return output.getvalue(),"jpg"

def replace_guest_document(registration: str, kind: str, image_data: str, filename: str|None=None, *, ignore_permissions: bool=False) -> dict:
    field={"id":"id_file","address":"address_proof_file"}.get((kind or "").lower())
    if not field:frappe.throw(_("Document kind must be id or address."))
    doc=frappe.get_doc("Hotel Guest Registration",registration)
    if not ignore_permissions:doc.check_permission("write")
    if doc.id_retention_mode=="Do Not Upload":frappe.throw(_("This registration is configured not to store documents."))
    content,ext=sanitize_guest_document(image_data)
    old=doc.get(field)
    from frappe.utils.file_manager import save_file
    file_doc=save_file(f"{doc.name}-{kind}.{ext}",content,doc.doctype,doc.name,is_private=1,df=field)
    doc.db_set(field,file_doc.file_url)
    if old and old!=file_doc.file_url:
        old_name=frappe.db.get_value("File",{"file_url":old},"name")
        if old_name:
            try:frappe.delete_doc("File",old_name,ignore_permissions=True,force=True)
            except Exception:frappe.log_error(frappe.get_traceback(),f"Unable to remove replaced guest document {old_name}")
    return {"registration":doc.name,"field":field,"file_url":file_doc.file_url}


def replace_occupant_document(registration: str, occupant_row: str, image_data: str, filename: str | None = None, *, ignore_permissions: bool = False) -> dict:
    registration_doc = frappe.get_doc("Hotel Guest Registration", registration)
    if not ignore_permissions:
        registration_doc.check_permission("write")
    if registration_doc.id_retention_mode == "Do Not Upload":
        frappe.throw(_("This registration is configured not to store documents."))
    occupant = next((row for row in registration_doc.occupants if row.name == occupant_row), None)
    if not occupant:
        frappe.throw(_("Occupant row was not found on this registration."))
    content, ext = sanitize_guest_document(image_data)
    old = occupant.get("id_file")
    from frappe.utils.file_manager import save_file
    file_doc = save_file(
        f"{registration_doc.name}-occupant-{occupant.idx}.{ext}", content,
        registration_doc.doctype, registration_doc.name, is_private=1,
    )
    frappe.db.set_value("Hotel Registered Occupant", occupant.name, {"id_file": file_doc.file_url, "id_verified": 0}, update_modified=False)
    if old and old != file_doc.file_url:
        old_name = frappe.db.get_value("File", {"file_url": old}, "name")
        if old_name:
            try:
                frappe.delete_doc("File", old_name, ignore_permissions=True, force=True)
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Unable to remove replaced occupant document {old_name}")
    return {"registration": registration_doc.name, "occupant": occupant.name, "file_url": file_doc.file_url}

def purge_registration_documents(registration: str, reason: str="Verify and Discard") -> dict:
    doc=frappe.get_doc("Hotel Guest Registration",registration);removed=[]
    for field in ("id_file","address_proof_file"):
        url=doc.get(field)
        if not url:continue
        file_name=frappe.db.get_value("File",{"file_url":url},"name")
        doc.db_set(field,None)
        if file_name:
            try:frappe.delete_doc("File",file_name,ignore_permissions=True,force=True);removed.append(file_name)
            except Exception:frappe.log_error(frappe.get_traceback(),f"Guest document purge failed {file_name}")
    for occupant in doc.occupants:
        url=occupant.get("id_file")
        if not url: continue
        file_name=frappe.db.get_value("File",{"file_url":url},"name")
        frappe.db.set_value("Hotel Registered Occupant",occupant.name,{"id_file":None,"id_verified":0},update_modified=False)
        if file_name:
            try:frappe.delete_doc("File",file_name,ignore_permissions=True,force=True);removed.append(file_name)
            except Exception:frappe.log_error(frappe.get_traceback(),f"Occupant document purge failed {file_name}")
    doc.db_set("documents_purged_at",frappe.utils.now_datetime())
    return {"registration":doc.name,"removed":removed,"reason":reason}

@frappe.whitelist()
def upload_guest_document_for_staff(registration: str, kind: str, image_data: str, filename: str|None=None) -> dict:
    frappe.only_for(["System Manager","Hotel Manager","Front Desk"])
    return replace_guest_document(registration,kind,image_data,filename,ignore_permissions=False)

@frappe.whitelist()
def purge_guest_documents_for_staff(registration: str, reason: str="Manual verified purge") -> dict:
    frappe.only_for(["System Manager","Hotel Manager","Front Desk"])
    return purge_registration_documents(registration,reason)

def purge_verify_discard_documents() -> dict:
    if not cint(frappe.db.get_single_value("Hotel PMS Settings","purge_verify_discard_documents_daily") or 0):return {"purged":0,"disabled":True}
    rows=frappe.get_all("Hotel Guest Registration",filters={"id_retention_mode":"Verify and Discard","documents_purged_at":["is","not set"]},fields=["name","reservation"],limit=500)
    purged=0
    for row in rows:
        status=frappe.db.get_value("Hotel Reservation",row.reservation,"status") if row.reservation else None
        if status in ("Checked Out","Cancelled","No Show"):
            purge_registration_documents(row.name,"Scheduled retention purge");purged+=1
    return {"purged":purged}
