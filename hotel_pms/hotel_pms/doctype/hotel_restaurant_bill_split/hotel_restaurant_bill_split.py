import frappe
from frappe.model.document import Document
from frappe.utils import flt


class HotelRestaurantBillSplit(Document):
    def validate(self):
        order = frappe.get_doc("Hotel Restaurant Order", self.restaurant_order)
        source_rows = {row.name: row for row in order.items if row.status != "Cancelled"}
        total = 0
        for row in self.lines:
            source = source_rows.get(row.order_item_row)
            if not source:
                frappe.throw("Bill split references an invalid or cancelled order item.")
            row.item_code = source.item_code
            row.item_name = source.item_name
            row.rate = source.rate
            already = frappe.db.sql(
                """select coalesce(sum(l.qty),0)
                   from `tabHotel Restaurant Bill Split Line` l
                   inner join `tabHotel Restaurant Bill Split` s on s.name=l.parent
                   where s.restaurant_order=%s and s.status!='Cancelled'
                     and s.name!=%s and l.order_item_row=%s""",
                (self.restaurant_order, self.name or "", row.order_item_row),
            )[0][0]
            if flt(already) + flt(row.qty) > flt(source.qty):
                frappe.throw("Bill split quantity exceeds the original order item quantity.")
            if row.qty <= 0:
                frappe.throw("Split quantity must be greater than zero.")
            row.amount = flt(row.qty) * flt(row.rate)
            total += row.amount
        self.amount = total
        if self.settlement_type == "Room Posting" and not self.folio:
            frappe.throw("Hotel Folio is required for room posting.")
        if self.settlement_type == "City Ledger" and not self.city_ledger_folio:
            frappe.throw("City Ledger Folio is required for city-ledger settlement.")
        if self.settlement_type in ("Cash", "Card", "UPI") and not self.mode_of_payment:
            frappe.throw("Mode of Payment is required for direct settlement.")
