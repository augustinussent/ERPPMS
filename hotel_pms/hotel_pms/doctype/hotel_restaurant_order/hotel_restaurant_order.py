from frappe.model.document import Document


class HotelRestaurantOrder(Document):
    def before_insert(self):
        from frappe.utils import now_datetime
        if not self.ordered_at:
            self.ordered_at = now_datetime()

    def validate(self):
        import frappe
        from frappe.utils import flt
        from hotel_pms.revenue_rules import tax_breakdown
        if self.service_type == "Dine In" and not self.table:
            frappe.throw("A table is required for dine-in orders.")
        if self.table:
            locked = frappe.db.sql(
                "select outlet, active_order from `tabHotel Restaurant Table` where name=%s for update",
                self.table,
                as_dict=True,
            )
            if not locked:
                frappe.throw("Restaurant table was not found.")
            table = locked[0]
            if table.outlet != self.outlet:
                frappe.throw("Table must belong to the selected outlet.")
            if table.active_order and table.active_order != self.name:
                active_status = frappe.db.get_value("Hotel Restaurant Order", table.active_order, "status")
                if active_status not in ("Billed", "Cancelled"):
                    frappe.throw("The selected table already has an active order.")
        if self.service_type == "Room Service" and not self.reservation:
            frappe.throw("A reservation is required for room-service orders.")
        if self.reservation:
            reservation = frappe.get_doc("Hotel Reservation", self.reservation)
            if reservation.status != "Checked In":
                frappe.throw("Room service can only be posted to a checked-in reservation.")
            self.property = reservation.property
            self.customer = self.customer or reservation.guest
            self.folio = self.folio or frappe.db.get_value("Hotel Folio", {"reservation": reservation.name}, "name")
            if not self.room and reservation.rooms:
                self.room = reservation.rooms[0].room
        outlet = frappe.get_doc("Hotel Outlet", self.outlet)
        if outlet.property != self.property:
            frappe.throw("Outlet and order property must match.")
        self.tax_profile = self.tax_profile or outlet.tax_profile
        subtotal = 0
        for row in self.items:
            if row.menu_item:
                menu = frappe.get_doc("Hotel Outlet Menu Item", row.menu_item)
                if menu.outlet != self.outlet or not menu.available:
                    frappe.throw("Menu item is not available for the selected outlet.")
                row.item_code = menu.item_code
                row.item_name = menu.menu_name
                row.rate = menu.rate
                row.kitchen_station = menu.kitchen_station
                row.course = menu.course
                row.allergy_alert = menu.allergy_alert
                row.preparation_minutes = menu.preparation_minutes
            if row.qty <= 0 or row.rate < 0:
                frappe.throw("Order item quantity must be positive and rate cannot be negative.")
            row.amount = flt(row.qty) * flt(row.rate)
            subtotal += row.amount
        self.subtotal = subtotal
        if self.tax_profile:
            profile = frappe.get_doc("Hotel Tax Profile", self.tax_profile)
            result = tax_breakdown(subtotal, profile.service_charge_rate, profile.tax_rate, profile.tax_basis, bool(profile.prices_include_service_charge), bool(profile.prices_include_tax), profile.rounding_method)
            self.service_charge_amount = result["service_charge"]
            self.tax_amount = result["tax"]
            self.grand_total = result["gross"]
        else:
            self.service_charge_amount = 0
            self.tax_amount = 0
            self.grand_total = subtotal
        if self.is_complimentary:
            if not self.complimentary_reason or not self.authorized_by:
                frappe.throw("Complimentary reason and authorizer are required.")
            previous = self.get_doc_before_save() if not self.is_new() else None
            authorization_changed = (
                previous is None
                or not previous.is_complimentary
                or previous.complimentary_reason != self.complimentary_reason
                or previous.authorized_by != self.authorized_by
            )
            if authorization_changed and not ({"Hotel Manager", "System Manager"} & set(frappe.get_roles())):
                frappe.throw("Only Hotel Manager can authorize or change a complimentary order.", frappe.PermissionError)
