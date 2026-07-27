from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

GRC_FORMAT = "Hotel Guest Registration Card"
CANCELLATION_FORMAT = "Hotel Cancellation Confirmation"


def setup_front_office() -> None:
    create_custom_fields(
        {
            "Payment Entry": [
                {"fieldname":"custom_hotel_reservation","label":"Hotel Reservation","fieldtype":"Link","options":"Hotel Reservation","insert_after":"party_name","read_only":1},
                {"fieldname":"custom_hotel_transaction_type","label":"Hotel Transaction Type","fieldtype":"Select","options":"Deposit\nRefund","insert_after":"custom_hotel_reservation","read_only":1},
            ],
        }, update=True,
    )
    _upsert_print_format(GRC_FORMAT, "Hotel Guest Registration", GRC_HTML)
    _upsert_print_format(CANCELLATION_FORMAT, "Hotel Cancellation", CANCELLATION_HTML)


def _upsert_print_format(name: str, doctype: str, html: str) -> None:
    values = {"print_format_for":"DocType","doc_type":doctype,"module":"Hotel PMS","standard":"No","custom_format":1,"print_format_type":"Jinja","disabled":0,"html":html}
    if frappe.db.exists("Print Format", name):
        doc=frappe.get_doc("Print Format",name); doc.update(values); doc.save(ignore_permissions=True)
    else:
        frappe.get_doc({"doctype":"Print Format","name":name,**values}).insert(ignore_permissions=True)


GRC_HTML = r"""
<style>.grc{font-size:10.5pt}.grc table{width:100%;border-collapse:collapse;margin:10px 0}.grc th,.grc td{border:1px solid #aaa;padding:6px;text-align:left}.grc h2{text-align:center}.signature{height:70px}</style>
<div class="grc">
<h2>GUEST REGISTRATION CARD</h2>
<table><tr><th>Registration</th><td>{{ doc.name }}</td><th>Reservation</th><td>{{ doc.reservation }}</td></tr>
<tr><th>Guest</th><td>{{ doc.guest }}</td><th>Stay</th><td>{{ frappe.utils.formatdate(doc.arrival_date) }} - {{ frappe.utils.formatdate(doc.departure_date) }}</td></tr>
<tr><th>Vehicle</th><td>{{ doc.vehicle_number or '-' }}</td><th>Status</th><td>{{ doc.status }}</td></tr></table>
<h4>Registered Occupants</h4><table><thead><tr><th>No</th><th>Full Name</th><th>Nationality</th><th>ID Type</th><th>ID Number</th></tr></thead><tbody>
{% for row in doc.occupants %}<tr><td>{{ loop.index }}</td><td>{{ row.full_name }}{% if row.is_primary_guest %} (Primary){% endif %}</td><td>{{ row.nationality or '' }}</td><td>{{ row.id_type or '' }}</td><td>{{ row.id_number or '' }}</td></tr>{% endfor %}
</tbody></table>
<p>I confirm that the information above is correct and agree to the hotel's terms, house rules, and privacy notice.</p>
<table><tr><td class="signature">Guest signature:<br><br>{{ doc.signature_name or '' }}</td><td class="signature">Verified by:<br><br>{{ doc.verified_by or '' }}</td></tr></table>
</div>
"""

CANCELLATION_HTML = r"""
<style>.cancel{font-size:11pt}.cancel table{width:100%;border-collapse:collapse;margin:15px 0}.cancel th,.cancel td{border:1px solid #aaa;padding:7px;text-align:left}</style>
<div class="cancel"><h2>Booking {{ doc.transaction_type }} Confirmation</h2>
<p>This letter confirms that reservation <strong>{{ doc.reservation }}</strong> has been processed as <strong>{{ doc.transaction_type }}</strong>.</p>
<table><tr><th>Confirmation Number</th><td>{{ doc.name }}</td><th>Date</th><td>{{ frappe.utils.formatdate(doc.transaction_date) }}</td></tr>
<tr><th>Reason</th><td colspan="3">{{ doc.reason }}</td></tr><tr><th>Original Stay Value</th><td>{{ doc.get_formatted('gross_stay_amount') }}</td><th>Final Fee</th><td>{{ doc.get_formatted('final_fee') }}</td></tr>
<tr><th>Deposit Received</th><td>{{ doc.get_formatted('deposit_received') }}</td><th>Estimated Refund Due</th><td>{{ doc.get_formatted('refund_due') }}</td></tr></table>
<p>Refunds, when applicable, remain subject to payment-channel processing and must be posted through ERPNext Payment Entry.</p></div>
"""
