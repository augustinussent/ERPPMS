from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

GROUP_ROLES = ["Hotel Sales", "Banquet"]
PRINT_FORMAT_NAME = "Hotel Group Confirmation Letter"


def setup_group_booking() -> None:
    for role_name in GROUP_ROLES:
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert(ignore_permissions=True)

    create_custom_fields(
        {
            "Quotation": [
                {
                    "fieldname": "custom_hotel_group_booking",
                    "label": "Hotel Group Booking",
                    "fieldtype": "Link",
                    "options": "Hotel Group Booking",
                    "insert_after": "party_name",
                    "read_only": 1,
                }
            ],
            "Sales Order": [
                {
                    "fieldname": "custom_hotel_group_booking",
                    "label": "Hotel Group Booking",
                    "fieldtype": "Link",
                    "options": "Hotel Group Booking",
                    "insert_after": "customer",
                    "read_only": 1,
                }
            ],
            "Sales Invoice": [
                {
                    "fieldname": "custom_hotel_group_booking",
                    "label": "Hotel Group Booking",
                    "fieldtype": "Link",
                    "options": "Hotel Group Booking",
                    "insert_after": "custom_hotel_folio",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_hotel_group_folio",
                    "label": "Hotel Group Folio",
                    "fieldtype": "Link",
                    "options": "Hotel Group Folio",
                    "insert_after": "custom_hotel_group_booking",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_hotel_group_sales_order",
                    "label": "Hotel Group Sales Order",
                    "fieldtype": "Link",
                    "options": "Sales Order",
                    "insert_after": "custom_hotel_group_folio",
                    "read_only": 1,
                },
            ],
            "Purchase Order": [
                {
                    "fieldname": "custom_hotel_group_booking",
                    "label": "Hotel Group Booking",
                    "fieldtype": "Link",
                    "options": "Hotel Group Booking",
                    "insert_after": "supplier",
                }
            ],
            "Purchase Invoice": [
                {
                    "fieldname": "custom_hotel_group_booking",
                    "label": "Hotel Group Booking",
                    "fieldtype": "Link",
                    "options": "Hotel Group Booking",
                    "insert_after": "supplier",
                }
            ],
            "Stock Entry": [
                {
                    "fieldname": "custom_hotel_group_booking",
                    "label": "Hotel Group Booking",
                    "fieldtype": "Link",
                    "options": "Hotel Group Booking",
                    "insert_after": "project",
                }
            ],
        },
        update=True,
    )
    _upsert_confirmation_print_format()


def _upsert_confirmation_print_format() -> None:
    values = {
        "print_format_for": "DocType",
        "doc_type": "Hotel Group Booking",
        "module": "Hotel PMS",
        "standard": "No",
        "custom_format": 1,
        "print_format_type": "Jinja",
        "disabled": 0,
        "html": CONFIRMATION_LETTER_HTML,
    }
    if frappe.db.exists("Print Format", PRINT_FORMAT_NAME):
        doc = frappe.get_doc("Print Format", PRINT_FORMAT_NAME)
        doc.update(values)
        doc.save(ignore_permissions=True)
    else:
        frappe.get_doc({"doctype": "Print Format", "name": PRINT_FORMAT_NAME, **values}).insert(ignore_permissions=True)


CONFIRMATION_LETTER_HTML = r"""
<style>
.confirmation-letter { font-size: 11pt; line-height: 1.45; color: #222; }
.confirmation-letter h2 { margin: 0 0 4px; font-size: 18pt; }
.confirmation-letter .muted { color: #666; }
.confirmation-letter .meta { width: 100%; margin: 14px 0 18px; }
.confirmation-letter .meta td { padding: 2px 0; vertical-align: top; }
.confirmation-letter table.details { width: 100%; border-collapse: collapse; margin: 10px 0 18px; }
.confirmation-letter table.details th, .confirmation-letter table.details td { border: 1px solid #bbb; padding: 6px; vertical-align: top; }
.confirmation-letter table.details th { background: #f3f3f3; }
.confirmation-letter .section-title { font-weight: 700; margin-top: 16px; margin-bottom: 5px; }
.confirmation-letter .signature { margin-top: 42px; }
.confirmation-letter .terms { font-size: 9.5pt; }
</style>
<div class="confirmation-letter">
  <table class="meta">
    <tr><td style="width:18%"><strong>Date</strong></td><td>: {{ frappe.utils.formatdate(doc.confirmation_letter_date or doc.inquiry_date) }}</td></tr>
    <tr><td><strong>Reference</strong></td><td>: {{ doc.name }}</td></tr>
    <tr><td><strong>To</strong></td><td>: {{ doc.confirmation_letter_contact_name or doc.contact_name or doc.customer }}<br>{{ doc.customer }}</td></tr>
    <tr><td><strong>Subject</strong></td><td>: <strong>{{ doc.confirmation_letter_subject or ("Booking Confirmation - " ~ doc.booking_name) }}</strong></td></tr>
  </table>

  <p>Dear {{ doc.confirmation_letter_contact_name or doc.contact_name or "Sir/Madam" }},</p>
  <p>{{ doc.confirmation_letter_intro or "Thank you for choosing our hotel. We are pleased to confirm the following group booking arrangements." }}</p>

  <div class="section-title">Booking Summary</div>
  <table class="details">
    <tr><th>Event / Group</th><td>{{ doc.booking_name }}</td><th>Status</th><td>{{ doc.status }}</td></tr>
    <tr><th>Arrival</th><td>{{ frappe.utils.formatdate(doc.arrival_date) }}</td><th>Departure</th><td>{{ frappe.utils.formatdate(doc.departure_date) }}</td></tr>
    <tr><th>Estimated Pax</th><td>{{ doc.estimated_pax or 0 }}</td><th>Guaranteed Pax</th><td>{{ doc.guaranteed_pax or 0 }}</td></tr>
    {% if doc.event_start %}
    <tr><th>Event Start</th><td>{{ frappe.utils.format_datetime(doc.event_start) }}</td><th>Event End</th><td>{{ frappe.utils.format_datetime(doc.event_end) }}</td></tr>
    {% endif %}
  </table>

  {% if doc.room_blocks %}
  <div class="section-title">Room Block</div>
  <table class="details">
    <thead><tr><th>Room Type</th><th>Stay Dates</th><th style="text-align:right">Rooms</th><th style="text-align:right">Indicative Rate</th><th>Cut-off</th></tr></thead>
    <tbody>
    {% for row in doc.room_blocks %}
      <tr>
        <td>{{ row.room_type }}</td>
        <td>{{ frappe.utils.formatdate(row.arrival_date) }} - {{ frappe.utils.formatdate(row.departure_date) }}</td>
        <td style="text-align:right">{{ row.rooms_blocked }}</td>
        <td style="text-align:right">{{ row.get_formatted("nightly_rate", doc) }}</td>
        <td>{{ frappe.utils.formatdate(row.release_date) if row.release_date else "-" }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% endif %}

  {% if doc.event_functions %}
  <div class="section-title">Meeting & Function Schedule</div>
  <table class="details">
    <thead><tr><th>Function</th><th>Date & Time</th><th>Venue / Setup</th><th style="text-align:right">Pax</th><th>Menu / Equipment</th></tr></thead>
    <tbody>
    {% for row in doc.event_functions if row.status != "Cancelled" %}
      <tr>
        <td>{{ row.function_name }}<br><span class="muted">{{ row.function_type }}</span></td>
        <td>{{ frappe.utils.format_datetime(row.start_datetime) }}<br>to {{ frappe.utils.format_datetime(row.end_datetime) }}</td>
        <td>{{ row.function_space or "-" }}<br>{{ row.setup_style or "" }}</td>
        <td style="text-align:right">{{ row.guaranteed_pax or row.billable_pax or row.estimated_pax or 0 }}</td>
        <td>{{ row.menu or "" }}{% if row.equipment %}<br>{{ row.equipment }}{% endif %}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% endif %}

  {% if doc.packages %}
  <div class="section-title">Package & Charges</div>
  <table class="details">
    <thead><tr><th>Package</th><th>Period</th><th>Basis</th><th style="text-align:right">Units</th><th style="text-align:right">Rate</th><th style="text-align:right">Amount</th></tr></thead>
    <tbody>
    {% for row in doc.packages %}
      <tr>
        <td>{{ row.package_template }}<br><span class="muted">{{ row.occupancy_type }}</span></td>
        <td>{{ frappe.utils.formatdate(row.date_from) }} - {{ frappe.utils.formatdate(row.date_to) }}</td>
        <td>{{ row.pricing_basis }}</td>
        <td style="text-align:right">{{ row.billable_units }}</td>
        <td style="text-align:right">{{ row.get_formatted("unit_rate", doc) }}</td>
        <td style="text-align:right">{{ row.get_formatted("amount", doc) }}</td>
      </tr>
    {% endfor %}
      <tr><th colspan="5" style="text-align:right">Package Total</th><th style="text-align:right">{{ doc.get_formatted("total_package_amount") }}</th></tr>
      {% if doc.deposit_amount %}<tr><th colspan="5" style="text-align:right">Required Deposit</th><th style="text-align:right">{{ doc.get_formatted("deposit_amount") }}</th></tr>{% endif %}
    </tbody>
  </table>
  {% endif %}

  {% if doc.deposit_schedules %}
  <div class="section-title">Deposit Schedule</div>
  <table class="details">
    <thead><tr><th>Milestone</th><th>Due Date</th><th style="text-align:right">Amount</th><th>Status</th></tr></thead>
    <tbody>
    {% for row in doc.deposit_schedules %}
      <tr>
        <td>{{ row.milestone }}</td>
        <td>{{ row.get_formatted("due_date", doc) }}</td>
        <td style="text-align:right">{{ row.get_formatted("amount", doc) }}</td>
        <td>{{ row.status }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% endif %}

  {% if doc.special_requirements %}
  <div class="section-title">Special Requirements</div>
  <div>{{ doc.special_requirements }}</div>
  {% endif %}

  {% if doc.confirmation_letter_terms %}
  <div class="section-title">Terms & Conditions</div>
  <div class="terms">{{ doc.confirmation_letter_terms }}</div>
  {% endif %}

  <p>Please sign or reply to this confirmation and complete the required deposit within the agreed deadline. Any amendment remains subject to availability and the latest issued confirmation.</p>

  <div class="signature">
    <p>Sincerely,</p>
    <br><br>
    <strong>{{ doc.confirmation_signatory_name or "Hotel Sales Team" }}</strong><br>
    {{ doc.confirmation_signatory_title or "Sales / Events" }}
  </div>
</div>
"""
