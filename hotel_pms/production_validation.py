from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, getdate, now_datetime

from hotel_pms import __version__
from hotel_pms.platform import assigned_properties, is_privileged
from hotel_pms.production_validation_rules import (
    BASE_REQUIRED_PARALLEL_METRICS,
    classify_parallel_row,
    promotion_blockers,
    rehearsal_matches,
    source_fingerprint as compute_source_fingerprint,
    summarize_parallel_rows,
)

DEPARTMENTS = {"Front Office","Housekeeping","Engineering","Sales & Banquet","F&B","Finance","IT","Management"}

REHEARSAL_TYPES = (
    "Blank Install",
    "Upgrade",
    "Restore",
    "Rollback",
    "Concurrency",
    "Performance",
    "Security",
    "Smoke",
)
def _require_manager() -> None:
    if not is_privileged() and "Hotel Manager" not in frappe.get_roles():
        frappe.throw(_("Hotel Manager or System Manager role required."), frappe.PermissionError)


def _require_system_manager() -> None:
    if not is_privileged():
        frappe.throw(_("System Manager role required."), frappe.PermissionError)


def _validate_property(property_name: str | None) -> None:
    if property_name and property_name not in assigned_properties():
        frappe.throw(_("Not permitted for this property."), frappe.PermissionError)


def _app_root() -> Path:
    return Path(__file__).resolve().parents[1]


def source_fingerprint(root: Path | None = None) -> str:
    return compute_source_fingerprint(root or _app_root())


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_text(value: str | None) -> str:
    return _sha256_bytes((value or "").encode("utf-8"))


def _file_checksum(file_url: str | None) -> str | None:
    if not file_url:
        return None
    file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if not file_name:
        return None
    try:
        path = Path(frappe.get_doc("File", file_name).get_full_path())
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            return digest.hexdigest()
    except Exception:
        return None
    return None


def current_environment() -> dict:
    import erpnext

    return {
        "release_version": __version__,
        "frappe_version": getattr(frappe, "__version__", ""),
        "erpnext_version": getattr(erpnext, "__version__", ""),
        "image_digest": getattr(frappe.conf, "hotel_pms_image_digest", None)
        or os.getenv("HOTEL_PMS_IMAGE_DIGEST")
        or "",
        "artifact_sha256": getattr(frappe.conf, "hotel_pms_artifact_sha256", None)
        or os.getenv("HOTEL_PMS_ARTIFACT_SHA256")
        or "",
        "source_fingerprint": source_fingerprint(),
    }


def _validate_sha256(value: str | None, label: str, required: bool = False) -> None:
    value = (value or "").strip().lower()
    if not value and not required:
        return
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        frappe.throw(_("{0} must be a 64-character SHA-256 value.").format(label))


@frappe.whitelist()
def create_release_manifest(
    promotion_target_version: str = "1.0.0",
    frappe_version: str | None = None,
    erpnext_version: str | None = None,
    image_digest: str | None = None,
    artifact_sha256: str | None = None,
    package_url: str | None = None,
    git_commit: str | None = None,
    notes: str | None = None,
) -> dict:
    _require_system_manager()
    env = current_environment()
    frappe_version = frappe_version or env["frappe_version"]
    erpnext_version = erpnext_version or env["erpnext_version"]
    image_digest = image_digest or env["image_digest"]
    if not frappe_version or not erpnext_version or not image_digest:
        frappe.throw(_("Pinned Frappe version, ERPNext version, and image digest are required."))
    if artifact_sha256:
        _validate_sha256(artifact_sha256, "Package SHA-256")
    existing = frappe.get_all(
        "Hotel Release Manifest",
        filters={"release_version": __version__, "source_fingerprint": env["source_fingerprint"], "status": ["!=", "Revoked"]},
        fields=["name"],
        limit=1,
    )
    if existing:
        return frappe.get_doc("Hotel Release Manifest", existing[0].name).as_dict()
    doc = frappe.get_doc(
        {
            "doctype": "Hotel Release Manifest",
            "release_version": __version__,
            "promotion_target_version": promotion_target_version,
            "status": "Draft",
            "source_fingerprint": env["source_fingerprint"],
            "artifact_sha256": artifact_sha256,
            "package_url": package_url,
            "git_commit": git_commit,
            "frappe_version": frappe_version,
            "erpnext_version": erpnext_version,
            "image_digest": image_digest,
            "created_at": now_datetime(),
            "created_by": frappe.session.user,
            "notes": notes,
        }
    )
    doc.flags.validation_internal_update = True
    doc.insert(ignore_permissions=True)
    return doc.as_dict()


@frappe.whitelist()
def freeze_release_manifest(manifest_name: str) -> dict:
    _require_system_manager()
    doc = frappe.get_doc("Hotel Release Manifest", manifest_name)
    if doc.status == "Promoted":
        return doc.as_dict()
    if doc.status != "Draft":
        frappe.throw(_("Only a Draft manifest can be frozen."))
    env = current_environment()
    blockers = []
    if doc.release_version != __version__:
        blockers.append("Manifest release version differs from the installed application.")
    if doc.source_fingerprint != env["source_fingerprint"]:
        blockers.append("Source fingerprint changed after manifest creation.")
    if doc.frappe_version != env["frappe_version"]:
        blockers.append("Frappe version differs from the manifest.")
    if doc.erpnext_version != env["erpnext_version"]:
        blockers.append("ERPNext version differs from the manifest.")
    if doc.image_digest != env["image_digest"]:
        blockers.append("Container image digest differs from the manifest.")
    if not doc.artifact_sha256:
        blockers.append("Package SHA-256 is required before freezing the manifest.")
    else:
        try:
            _validate_sha256(doc.artifact_sha256, "Package SHA-256", required=True)
        except Exception as exc:
            blockers.append(str(exc))
    if not env.get("artifact_sha256"):
        blockers.append("Installed candidate package checksum is not configured in HOTEL_PMS_ARTIFACT_SHA256.")
    elif doc.artifact_sha256 != env.get("artifact_sha256"):
        blockers.append("Installed candidate package checksum differs from the manifest.")
    if blockers:
        frappe.throw("\n".join(blockers))
    doc.status = "Frozen"
    doc.frozen_at = now_datetime()
    doc.frozen_by = frappe.session.user
    doc.flags.validation_internal_update = True
    doc.save(ignore_permissions=True)
    return doc.as_dict()


def verify_release_manifest(manifest_name: str | None) -> dict:
    if not manifest_name:
        return {"passed": False, "blockers": ["No release manifest selected."]}
    doc = frappe.get_doc("Hotel Release Manifest", manifest_name)
    env = current_environment()
    blockers = []
    if doc.status not in ("Frozen", "Promotion Prepared", "Promoted"):
        blockers.append("Release manifest is not frozen or prepared for promotion.")
    use_final=doc.status in ("Promotion Prepared","Promoted")
    expected_release=doc.promotion_target_version if use_final else doc.release_version
    expected_image=doc.promoted_image_digest if use_final else doc.image_digest
    expected_artifact=doc.promoted_artifact_sha256 if use_final else doc.artifact_sha256
    comparisons=(
        (expected_release,env.get("release_version"),"release version"),
        (doc.source_fingerprint,env.get("source_fingerprint"),"source fingerprint"),
        (doc.frappe_version,env.get("frappe_version"),"Frappe version"),
        (doc.erpnext_version,env.get("erpnext_version"),"ERPNext version"),
        (expected_image,env.get("image_digest"),"image digest"),
        (expected_artifact,env.get("artifact_sha256"),"package checksum"),
    )
    for expected,actual,label in comparisons:
        if not expected or expected != actual:
            blockers.append(f"Installed {label} differs from the frozen manifest.")
    return {"passed": not blockers, "blockers": blockers, "manifest": doc.as_dict(), "environment": env}


@frappe.whitelist()
def verify_installed_release(manifest_name: str) -> dict:
    _require_system_manager()
    result=verify_release_manifest(manifest_name)
    if not result.get("passed"):
        return result
    manifest=frappe.get_doc("Hotel Release Manifest",manifest_name)
    if manifest.status=="Promotion Prepared":
        manifest.status="Promoted"; manifest.promoted_at=now_datetime(); manifest.promoted_by=frappe.session.user
        manifest.flags.validation_internal_update=True; manifest.save(ignore_permissions=True)
        if manifest.gate_run:
            gate=frappe.get_doc("Hotel Production Gate Run",manifest.gate_run)
            gate.promotion_status="Promoted"; gate.promoted_at=now_datetime(); gate.promoted_by=frappe.session.user
            gate.flags.production_gate_internal_update=True; gate.save(ignore_permissions=True)
        result["manifest"]=manifest.as_dict(); result["finalized_promotion"]=True
    return result


@frappe.whitelist()
def record_rehearsal(
    run_type: str,
    environment_name: str,
    status: str,
    started_at,
    completed_at,
    property: str | None = None,
    source_version: str | None = None,
    result_summary: str | None = None,
    command: str | None = None,
    evidence_file: str | None = None,
    evidence_url: str | None = None,
    evidence_sha256: str | None = None,
    measured_rto_minutes: float | None = None,
    metadata_json: str | dict | None = None,
) -> dict:
    _require_manager()
    _validate_property(property)
    if run_type not in REHEARSAL_TYPES:
        frappe.throw(_("Invalid rehearsal type."))
    if status not in ("Passed", "Failed"):
        frappe.throw(_("Invalid rehearsal status."))
    start = get_datetime(started_at)
    end = get_datetime(completed_at)
    if end < start:
        frappe.throw(_("Completed time cannot be earlier than start time."))
    metadata = json.loads(metadata_json) if isinstance(metadata_json, str) and metadata_json else (metadata_json or {})
    evidence_sha256 = evidence_sha256 or _file_checksum(evidence_file)
    if status == "Passed" and not (evidence_sha256 or evidence_url or result_summary):
        frappe.throw(_("Passed rehearsals require immutable evidence or a result summary."))
    evidence_sha256=evidence_sha256 or _sha256_text(json.dumps({"result_summary":result_summary,"evidence_url":evidence_url,"metadata":metadata},sort_keys=True,default=str))
    _validate_sha256(evidence_sha256, "Evidence SHA-256", required=True)
    env = current_environment()
    doc = frappe.get_doc(
        {
            "doctype": "Hotel Rehearsal Run",
            "property": property,
            "run_type": run_type,
            "environment_name": environment_name,
            "release_version": __version__,
            "source_version": source_version,
            "status": status,
            "started_at": start,
            "completed_at": end,
            "duration_seconds": (end - start).total_seconds(),
            "measured_rto_minutes": flt(measured_rto_minutes),
            "executed_by": frappe.session.user,
            "source_fingerprint": env["source_fingerprint"],
            "image_digest": env["image_digest"],
            "command_hash": _sha256_text(command) if command else None,
            "result_summary": result_summary,
            "evidence_file": evidence_file,
            "evidence_url": evidence_url,
            "evidence_sha256": evidence_sha256,
            "metadata_json": json.dumps(metadata, sort_keys=True, default=str),
        }
    )
    doc.flags.validation_internal_update = True
    doc.insert(ignore_permissions=True)
    return doc.as_dict()


def required_parallel_metrics(property_name: str) -> set[str]:
    required=set(BASE_REQUIRED_PARALLEL_METRICS)
    if frappe.db.exists("Hotel Restaurant Order",{"property":property_name}):
        required.update({"FNB_REVENUE","STOCK_MOVEMENT"})
    return required


@frappe.whitelist()
def create_parallel_run_batch(
    property: str,
    source_system: str,
    from_date,
    to_date,
    rows: str | list,
    default_tolerance: float = 0,
    source_file: str | None = None,
    evidence_sha256: str | None = None,
    notes: str | None = None,
) -> dict:
    _require_manager()
    _validate_property(property)
    parsed = json.loads(rows) if isinstance(rows, str) else rows
    if not isinstance(parsed, list) or not parsed:
        frappe.throw(_("At least one parallel-run row is required."))
    if getdate(to_date) < getdate(from_date):
        frappe.throw(_("Parallel-run To Date cannot be before From Date."))
    evidence_sha256 = evidence_sha256 or _file_checksum(source_file)
    if evidence_sha256:
        _validate_sha256(evidence_sha256, "Evidence SHA-256")
    normalized = []
    for index, row in enumerate(parsed, start=1):
        code = str(row.get("metric_code") or "").strip().upper()
        department = str(row.get("department") or "").strip()
        if not code or not department:
            frappe.throw(_("Row {0}: metric_code and department are required.").format(index))
        if department not in DEPARTMENTS:
            frappe.throw(_("Row {0}: invalid department {1}.").format(index,department))
        try:
            legacy_value=float(row.get("legacy_value"))
            pms_value=float(row.get("pms_value"))
            tolerance=float(row.get("tolerance") if row.get("tolerance") not in (None,"") else default_tolerance)
        except (TypeError,ValueError):
            frappe.throw(_("Row {0}: legacy_value, pms_value, and tolerance must be numeric.").format(index))
        if tolerance < 0:
            frappe.throw(_("Row {0}: tolerance cannot be negative.").format(index))
        status, variance = classify_parallel_row(legacy_value, pms_value, tolerance)
        normalized.append(
            {
                "metric_code": code,
                "department": department,
                "business_date": row.get("business_date"),
                "reference": row.get("reference"),
                "legacy_value": legacy_value,
                "pms_value": pms_value,
                "variance": float(variance),
                "tolerance": tolerance,
                "status": status,
                "notes": row.get("notes"),
            }
        )
    summary = summarize_parallel_rows(normalized)
    missing_metrics=sorted(required_parallel_metrics(property)-{row["metric_code"] for row in normalized})
    if missing_metrics:
        summary["status"]="Failed"
    evidence_sha256=evidence_sha256 or _sha256_text(json.dumps(normalized,sort_keys=True,default=str))
    doc = frappe.get_doc(
        {
            "doctype": "Hotel Parallel Run Batch",
            "property": property,
            "source_system": source_system,
            "from_date": from_date,
            "to_date": to_date,
            "status": summary["status"],
            "total_rows": summary["total"],
            "passed_rows": summary["passed"],
            "warning_rows": summary["warnings"],
            "failed_rows": summary["failed"],
            "default_tolerance": flt(default_tolerance),
            "created_at": now_datetime(),
            "created_by": frappe.session.user,
            "reviewed_at": now_datetime(),
            "reviewed_by": frappe.session.user,
            "source_file": source_file,
            "evidence_sha256": evidence_sha256,
            "missing_metrics": ", ".join(missing_metrics),
            "notes": "\n".join(filter(None,[notes, f"Missing mandatory metrics: {', '.join(missing_metrics)}" if missing_metrics else None])),
            "rows": normalized,
        }
    )
    doc.flags.validation_internal_update = True
    doc.insert(ignore_permissions=True)
    return doc.as_dict()


@frappe.whitelist()
def create_parallel_run_batch_from_csv(property: str, source_system: str, from_date, to_date, source_file: str, default_tolerance: float = 0, notes: str | None = None) -> dict:
    _require_manager(); _validate_property(property)
    file_name=frappe.db.get_value("File",{"file_url":source_file},"name")
    if not file_name:
        frappe.throw(_("Source file was not found."))
    path=Path(frappe.get_doc("File",file_name).get_full_path())
    if path.suffix.lower() != ".csv":
        frappe.throw(_("Parallel-run source must be a CSV file."))
    with path.open("r",encoding="utf-8-sig",newline="") as handle:
        rows=list(csv.DictReader(handle))
    return create_parallel_run_batch(property,source_system,from_date,to_date,rows,default_tolerance,source_file,_file_checksum(source_file),notes)


@frappe.whitelist()
def create_validation_evidence(
    gate_run: str,
    check_code: str,
    evidence_type: str,
    evidence_file: str | None = None,
    external_url: str | None = None,
    description: str | None = None,
    checksum_sha256: str | None = None,
    metadata_json: str | dict | None = None,
) -> dict:
    _require_manager()
    gate = frappe.get_doc("Hotel Production Gate Run", gate_run)
    _validate_property(gate.property)
    if evidence_type not in ("File", "URL", "Text", "Command Output"):
        frappe.throw(_("Invalid evidence type."))
    if check_code not in {"FINAL_DECISION","RELEASE_PROMOTION"} and not any(row.check_code == check_code for row in gate.checks):
        frappe.throw(_("Check code does not exist on this gate run."))
    checksum_sha256 = checksum_sha256 or _file_checksum(evidence_file)
    if not checksum_sha256:
        checksum_sha256 = _sha256_text(json.dumps({"url": external_url, "description": description}, sort_keys=True))
    _validate_sha256(checksum_sha256, "Evidence SHA-256", required=True)
    metadata = json.loads(metadata_json) if isinstance(metadata_json, str) and metadata_json else (metadata_json or {})
    doc = frappe.get_doc(
        {
            "doctype": "Hotel Validation Evidence",
            "gate_run": gate_run,
            "property": gate.property,
            "check_code": check_code,
            "evidence_type": evidence_type,
            "evidence_file": evidence_file,
            "external_url": external_url,
            "description": description,
            "checksum_sha256": checksum_sha256,
            "metadata_json": json.dumps(metadata, sort_keys=True, default=str),
            "captured_at": now_datetime(),
            "captured_by": frappe.session.user,
        }
    )
    doc.flags.validation_internal_update = True
    doc.insert(ignore_permissions=True)
    return doc.as_dict()


def _latest_rehearsal(run_type: str, gate, manifest) -> dict | None:
    filters = {
        "run_type": run_type,
        "release_version": gate.release_version,
        "environment_name": gate.environment_name,
    }
    if gate.property:
        filters["property"] = gate.property
    else:
        filters["property"] = ["is", "not set"]
    rows = frappe.get_all(
        "Hotel Rehearsal Run",
        filters=filters,
        fields=["name", "run_type", "status", "release_version", "source_fingerprint", "image_digest", "completed_at", "evidence_sha256"],
        order_by="completed_at desc",
        limit=1,
    )
    return rows[0] if rows else None


def _latest_parallel_batch(gate) -> dict | None:
    if gate.property:
        rows = frappe.get_all(
            "Hotel Parallel Run Batch",
            filters={"property": gate.property},
            fields=["name", "property", "status", "total_rows", "passed_rows", "warning_rows", "failed_rows", "missing_metrics", "from_date", "to_date", "evidence_sha256"],
            order_by="to_date desc, creation desc",
            limit=1,
        )
        return rows[0] if rows else None
    properties=frappe.get_all("Hotel Property",filters={"enabled":1},pluck="name")
    batches=[]
    for property_name in properties:
        rows=frappe.get_all("Hotel Parallel Run Batch",filters={"property":property_name},fields=["name","property","status","total_rows","passed_rows","warning_rows","failed_rows","missing_metrics","from_date","to_date","evidence_sha256"],order_by="to_date desc, creation desc",limit=1)
        if rows: batches.append(rows[0])
        else: batches.append({"property":property_name,"status":"Missing"})
    status="Passed" if batches and all(row.get("status")=="Passed" for row in batches) else ("Warning" if batches and all(row.get("status") in ("Passed","Warning") for row in batches) else "Failed")
    return {"name":f"{len(batches)} property batches","status":status,"batches":batches,"total_rows":sum(int(row.get("total_rows") or 0) for row in batches),"warning_rows":sum(int(row.get("warning_rows") or 0) for row in batches),"failed_rows":sum(int(row.get("failed_rows") or 0) for row in batches)}


def validation_gate_results(gate) -> dict:
    manifest_result = verify_release_manifest(gate.release_manifest) if gate.release_manifest else {"passed": False, "blockers": ["No release manifest selected."]}
    manifest = manifest_result.get("manifest") or {}
    source_hash = manifest.get("source_fingerprint")
    image_digest = manifest.get("image_digest")
    rehearsals = {}
    for run_type in REHEARSAL_TYPES:
        row = _latest_rehearsal(run_type, gate, manifest)
        rehearsals[run_type] = {
            "record": row,
            "passed": rehearsal_matches(row, gate.release_version, source_hash, image_digest),
        }
    parallel = _latest_parallel_batch(gate)
    parallel_status = parallel.get("status") if parallel else "Missing"
    return {
        "manifest": manifest_result,
        "rehearsals": rehearsals,
        "parallel": parallel,
        "parallel_status": parallel_status,
    }


@frappe.whitelist()
def prepare_release_promotion(run_name: str, manifest_name: str, promoted_artifact_sha256: str, promoted_image_digest: str, promoted_package_url: str | None = None, notes: str | None = None) -> dict:
    _require_system_manager()
    gate = frappe.get_doc("Hotel Production Gate Run", run_name)
    manifest = frappe.get_doc("Hotel Release Manifest", manifest_name)
    if gate.release_manifest != manifest.name:
        frappe.throw(_("Gate run and release manifest do not match."))
    if manifest.status in ("Promotion Prepared","Promoted"):
        return {"gate": gate.as_dict(), "manifest": manifest.as_dict()}
    _validate_sha256(promoted_artifact_sha256,"Promoted Package SHA-256",required=True)
    if not promoted_image_digest:
        frappe.throw(_("Promoted image digest is required."))
    validation = validation_gate_results(gate)
    rehearsal_statuses = {key: value["passed"] for key, value in validation["rehearsals"].items()}
    blockers = validation["manifest"].get("blockers", []) + promotion_blockers(
        gate.as_dict(), manifest.as_dict(), rehearsal_statuses, validation["parallel_status"]
    )
    if blockers:
        frappe.throw("\n".join(dict.fromkeys(blockers)))
    evidence=create_validation_evidence(run_name,"RELEASE_PROMOTION","Text",description=notes or manifest.promotion_target_version,metadata_json={"manifest":manifest.name,"target_version":manifest.promotion_target_version})
    manifest.status = "Promotion Prepared"
    manifest.promoted_artifact_sha256=promoted_artifact_sha256
    manifest.promoted_image_digest=promoted_image_digest
    manifest.promoted_package_url=promoted_package_url
    manifest.gate_run = gate.name
    manifest.notes = "\n".join(filter(None, [manifest.notes, notes, f"Promotion evidence: {evidence.name}"]))
    manifest.flags.validation_internal_update = True
    manifest.save(ignore_permissions=True)
    gate.promotion_status = "Promotion Prepared"
    gate.flags.production_gate_internal_update = True
    gate.save(ignore_permissions=True)
    return {"gate": gate.as_dict(), "manifest": manifest.as_dict()}


@frappe.whitelist()
def promote_release(run_name: str, manifest_name: str, promoted_artifact_sha256: str, promoted_image_digest: str, promoted_package_url: str | None = None, notes: str | None = None) -> dict:
    return prepare_release_promotion(run_name,manifest_name,promoted_artifact_sha256,promoted_image_digest,promoted_package_url,notes)


@frappe.whitelist()
def get_validation_dashboard(run_name: str | None = None) -> dict:
    _require_manager()
    if not run_name:
        return {
            "manifests": frappe.get_all(
                "Hotel Release Manifest",
                fields=["name", "release_version", "promotion_target_version", "status", "source_fingerprint", "image_digest", "modified"],
                order_by="modified desc",
                limit=20,
            ),
            "rehearsals": frappe.get_all(
                "Hotel Rehearsal Run",
                fields=["name", "property", "run_type", "environment_name", "release_version", "status", "completed_at"],
                order_by="completed_at desc",
                limit=20,
            ),
        }
    gate = frappe.get_doc("Hotel Production Gate Run", run_name)
    _validate_property(gate.property)
    return validation_gate_results(gate)
