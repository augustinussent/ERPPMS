
from __future__ import annotations
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from hotel_pms.setup_front_office import _upsert_print_format

RESERVATION_CONFIRMATION = "Hotel Reservation Confirmation"

def setup_guest_facing() -> None:
    create_custom_fields({
        "Customer":[{"fieldname":"custom_hotel_guest_profile","label":"Hotel Guest Profile","fieldtype":"Link","options":"Hotel Guest Profile","insert_after":"customer_name","read_only":1,"unique":1,"no_copy":1}],
        "Sales Order":[{"fieldname":"custom_hotel_reservation","label":"Hotel Reservation","fieldtype":"Link","options":"Hotel Reservation","insert_after":"customer","read_only":1,"no_copy":1}],
        "Payment Request":[{"fieldname":"custom_hotel_guest_token","label":"Guest Token Record","fieldtype":"Link","options":"Hotel Guest Access Token","insert_after":"custom_hotel_sync_key","read_only":1,"hidden":1,"no_copy":1}],
    }, update=True)
    _upsert_print_format(RESERVATION_CONFIRMATION,"Hotel Reservation",CONFIRMATION_HTML)
    _add_indexes()

def _add_indexes():
    for doctype, fields in {
        "Hotel Guest Access Token":["token_hash","status","expires_at"],
        "Hotel Guest Profile":["customer","status"],
        "Hotel Guest Blacklist":["customer","status","valid_until"],
        "Hotel Guest Action Log":["reservation","creation"],
    }.items():
        try: frappe.db.add_index(doctype,fields)
        except Exception: pass

CONFIRMATION_HTML=r"""
<style>.hc{font-size:11pt}.hc table{width:100%;border-collapse:collapse;margin:12px 0}.hc th,.hc td{border:1px solid #aaa;padding:7px;text-align:left}.hc h2{text-align:center}</style>
<div class="hc"><h2>BOOKING CONFIRMATION</h2>
<p>Thank you for choosing {{ doc.property }}. This confirms reservation <strong>{{ doc.name }}</strong>.</p>
<table><tr><th>Guest</th><td>{{ doc.guest }}</td><th>Status</th><td>{{ doc.status }}</td></tr>
<tr><th>Arrival</th><td>{{ frappe.utils.formatdate(doc.arrival_date) }}</td><th>Departure</th><td>{{ frappe.utils.formatdate(doc.departure_date) }}</td></tr>
<tr><th>Adults / Children</th><td>{{ doc.adults }} / {{ doc.children }}</td><th>Grand Total</th><td>{{ doc.get_formatted('quoted_grand_total') }}</td></tr></table>
<h4>Rooms</h4><table><thead><tr><th>Room Type</th><th>Rate Plan</th><th>Nightly Rate</th></tr></thead><tbody>
{% for row in doc.rooms %}<tr><td>{{ row.room_type }}</td><td>{{ row.rate_plan or '-' }}</td><td>{{ row.get_formatted('nightly_rate') }}</td></tr>{% endfor %}</tbody></table>
<p>Cancellation and deposit conditions follow the policy attached to this reservation.</p></div>
"""
