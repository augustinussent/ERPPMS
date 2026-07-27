from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    conditions = ["gb.docstatus < 2"]
    values = {}
    if filters.property:
        conditions.append("gb.property = %(property)s")
        values["property"] = filters.property
    if filters.from_date:
        conditions.append("gb.arrival_date >= %(from_date)s")
        values["from_date"] = filters.from_date
    if filters.to_date:
        conditions.append("gb.arrival_date <= %(to_date)s")
        values["to_date"] = filters.to_date
    if filters.status:
        conditions.append("gb.status = %(status)s")
        values["status"] = filters.status

    rows = frappe.db.sql(
        f"""
        select
            gb.name as group_booking,
            gb.booking_name,
            gb.customer,
            gb.status,
            gb.arrival_date,
            gb.departure_date,
            gb.currency,
            gb.total_package_amount as contracted_amount,
            coalesce(si.invoiced_revenue, 0) as invoiced_revenue,
            coalesce(si.outstanding_amount, 0) as outstanding_amount,
            coalesce(pi.direct_cost, 0) as direct_cost
        from `tabHotel Group Booking` gb
        left join (
            select custom_hotel_group_booking,
                   sum(base_net_total) as invoiced_revenue,
                   sum(outstanding_amount) as outstanding_amount
            from `tabSales Invoice`
            where docstatus = 1 and is_return = 0 and custom_hotel_group_booking is not null
            group by custom_hotel_group_booking
        ) si on si.custom_hotel_group_booking = gb.name
        left join (
            select custom_hotel_group_booking,
                   sum(base_net_total) as direct_cost
            from `tabPurchase Invoice`
            where docstatus = 1 and is_return = 0 and custom_hotel_group_booking is not null
            group by custom_hotel_group_booking
        ) pi on pi.custom_hotel_group_booking = gb.name
        where {' and '.join(conditions)}
        order by gb.arrival_date desc, gb.name desc
        """,
        values,
        as_dict=True,
    )

    for row in rows:
        row.gross_contribution = flt(row.invoiced_revenue) - flt(row.direct_cost)
        row.margin_percent = (row.gross_contribution / row.invoiced_revenue * 100) if row.invoiced_revenue else 0

    columns = [
        {"label": _("Group Booking"), "fieldname": "group_booking", "fieldtype": "Link", "options": "Hotel Group Booking", "width": 150},
        {"label": _("Event / Group"), "fieldname": "booking_name", "fieldtype": "Data", "width": 220},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": _("Arrival"), "fieldname": "arrival_date", "fieldtype": "Date", "width": 100},
        {"label": _("Departure"), "fieldname": "departure_date", "fieldtype": "Date", "width": 100},
        {"label": _("Contracted"), "fieldname": "contracted_amount", "fieldtype": "Currency", "options": "currency", "width": 130},
        {"label": _("Invoiced Revenue"), "fieldname": "invoiced_revenue", "fieldtype": "Currency", "options": "currency", "width": 140},
        {"label": _("Outstanding"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "options": "currency", "width": 130},
        {"label": _("Direct Cost"), "fieldname": "direct_cost", "fieldtype": "Currency", "options": "currency", "width": 130},
        {"label": _("Gross Contribution"), "fieldname": "gross_contribution", "fieldtype": "Currency", "options": "currency", "width": 150},
        {"label": _("Margin %"), "fieldname": "margin_percent", "fieldtype": "Percent", "width": 90},
    ]
    return columns, rows
