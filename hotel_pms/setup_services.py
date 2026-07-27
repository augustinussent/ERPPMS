from __future__ import annotations
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from hotel_pms.setup_front_office import _upsert_print_format
ROLES=["Restaurant Cashier","Restaurant Captain","Kitchen","Laundry","Guest Services"]

KOT_PRINT_FORMAT = "Hotel Kitchen Ticket 80mm"
LAUNDRY_PRINT_FORMAT = "Hotel Laundry Docket"

def setup_services():
    for role_name in ROLES:
        if not frappe.db.exists("Role",role_name): frappe.get_doc({"doctype":"Role","role_name":role_name}).insert(ignore_permissions=True)
    create_custom_fields({
      "POS Invoice":[
        {"fieldname":"custom_hotel_restaurant_order","label":"Hotel Restaurant Order","fieldtype":"Link","options":"Hotel Restaurant Order","insert_after":"custom_hotel_cashier_shift","read_only":1,"no_copy":1},
        {"fieldname":"custom_hotel_restaurant_split","label":"Hotel Restaurant Bill Split","fieldtype":"Link","options":"Hotel Restaurant Bill Split","insert_after":"custom_hotel_restaurant_order","read_only":1,"no_copy":1},
        {"fieldname":"custom_hotel_sync_key","label":"Hotel PMS Sync Key","fieldtype":"Data","insert_after":"custom_hotel_restaurant_split","read_only":1,"hidden":1,"unique":1,"no_copy":1},
      ],
      "Sales Invoice":[
        {"fieldname":"custom_hotel_restaurant_order","label":"Hotel Restaurant Order","fieldtype":"Link","options":"Hotel Restaurant Order","insert_after":"custom_hotel_tax_profile","read_only":1,"no_copy":1},
        {"fieldname":"custom_hotel_restaurant_split","label":"Hotel Restaurant Bill Split","fieldtype":"Link","options":"Hotel Restaurant Bill Split","insert_after":"custom_hotel_restaurant_order","read_only":1,"no_copy":1},
      ],
    },update=True)
    _upsert_print_format(KOT_PRINT_FORMAT, "Hotel Kitchen Ticket", KOT_HTML)
    _upsert_print_format(LAUNDRY_PRINT_FORMAT, "Hotel Laundry Order", LAUNDRY_HTML)
    for dt,fields in {"Hotel Restaurant Order":["outlet","status","table"],"Hotel Kitchen Ticket":["outlet","status","kitchen_station"],"Hotel Laundry Order":["property","status","promised_ready_at"],"Hotel Experience Booking":["experience","scheduled_at","status"]}.items():
        try: frappe.db.add_index(dt,fields)
        except Exception: pass


KOT_HTML = r"""<style>@page{size:80mm auto;margin:3mm}body{font-family:monospace;font-size:11px}.c{text-align:center}.line{border-top:1px dashed #000;margin:5px 0}.item{font-size:14px;font-weight:bold}</style><div class="c"><b>{{ doc.outlet }}</b><br>KOT #{{ doc.daily_kot_number }} · {{ doc.kitchen_station }}<br>{{ doc.restaurant_order }} · {{ doc.sent_at }}</div><div class="line"></div>{% for row in doc.items %}<div class="item">{{ row.qty }} × {{ row.item_name }}</div>{% if row.notes %}<div>{{ row.notes }}</div>{% endif %}{% endfor %}<div class="line"></div>"""

LAUNDRY_HTML = r"""<style>table{width:100%;border-collapse:collapse}th,td{border:1px solid #999;padding:6px}</style><h3>LAUNDRY DOCKET {{ doc.name }}</h3><p>Room: {{ doc.room or '-' }} · Reservation: {{ doc.reservation or '-' }}<br>Requested: {{ doc.requested_at }} · Promised: {{ doc.promised_ready_at }}</p><table><tr><th>Item</th><th>Sent</th><th>Returned</th><th>Rate</th></tr>{% for row in doc.items %}<tr><td>{{ row.description }}</td><td>{{ row.qty_sent }}</td><td>{{ row.qty_returned }}</td><td>{{ row.get_formatted('rate') }}</td></tr>{% endfor %}</table><p>Total: {{ doc.get_formatted('total_amount') }}</p>"""
