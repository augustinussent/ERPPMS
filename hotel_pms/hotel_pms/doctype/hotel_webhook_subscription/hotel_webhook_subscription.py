from urllib.parse import urlparse
import socket, ipaddress
import frappe
from frappe import _
from frappe.model.document import Document

def validate_webhook_url(url):
    parsed=urlparse(url or "")
    if parsed.scheme != "https" or not parsed.hostname:
        frappe.throw(_("Webhook endpoint must be a valid HTTPS URL."))
    try:
        addresses=socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        frappe.throw(_("Webhook hostname could not be resolved: {0}").format(exc))
    for info in addresses:
        address=ipaddress.ip_address(info[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast:
            frappe.throw(_("Webhook endpoint must not resolve to a private or reserved address."))
    return parsed

class HotelWebhookSubscription(Document):
    def validate(self):
        validate_webhook_url(self.endpoint_url)
        self.timeout_seconds=max(3,min(int(self.timeout_seconds or 15),60))
        self.max_attempts=max(1,min(int(self.max_attempts or 8),20))
