from __future__ import annotations

import frappe
from frappe.utils import strip_html


def users_with_roles(roles: list[str] | tuple[str, ...] | set[str], property_name: str | None = None) -> list[str]:
    roles = [role for role in roles if role]
    if not roles:
        return []
    users = frappe.get_all(
        "Has Role",
        filters={"role": ("in", roles), "parenttype": "User"},
        pluck="parent",
    )
    enabled = set(frappe.get_all("User", filters={"enabled": 1, "name": ("in", users)}, pluck="name")) if users else set()
    # Property scoping is intentionally left to User Permission. Sending to an enabled
    # role holder is safer than silently dropping an urgent room notification because a
    # property permission was configured inconsistently.
    return sorted(user for user in users if user in enabled and user not in ("Guest",))


def notify_users(
    users: list[str] | tuple[str, ...] | set[str],
    *,
    subject: str,
    message: str,
    document_type: str | None = None,
    document_name: str | None = None,
    event: str = "hotel_operations_update",
    payload: dict | None = None,
    dedupe_key: str | None = None,
) -> None:
    if frappe.db.exists("DocType", "Hotel PMS Settings"):
        enabled = frappe.db.get_single_value("Hotel PMS Settings", "enable_realtime_operations_notifications")
        if enabled is not None and not int(enabled or 0):
            return
    clean_users = sorted({u for u in users if u and u != "Guest"})
    for user in clean_users:
        if dedupe_key:
            cache_key = f"hotel_pms:notify:{dedupe_key}:{user}"
            if frappe.cache().get_value(cache_key):
                continue
            frappe.cache().set_value(cache_key, 1, expires_in_sec=3600)
        data = {"subject": subject, "message": strip_html(message), "document_type": document_type, "document_name": document_name}
        if payload:
            data.update(payload)
        frappe.publish_realtime(event, data, user=user, after_commit=True)
        try:
            frappe.get_doc(
                {
                    "doctype": "Notification Log",
                    "subject": subject,
                    "email_content": message,
                    "for_user": user,
                    "type": "Alert",
                    "document_type": document_type,
                    "document_name": document_name,
                    "from_user": frappe.session.user if frappe.session.user != "Guest" else "Administrator",
                }
            ).insert(ignore_permissions=True)
        except Exception:
            # Realtime delivery must not fail the operational transaction merely because
            # a Frappe release changes an optional Notification Log field.
            frappe.log_error(frappe.get_traceback(), "Hotel PMS notification log")


def notify_roles(roles, **kwargs) -> None:
    notify_users(users_with_roles(roles, kwargs.pop("property_name", None)), **kwargs)
