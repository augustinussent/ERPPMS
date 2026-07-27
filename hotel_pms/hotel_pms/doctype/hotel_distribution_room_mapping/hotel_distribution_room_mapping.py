from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class HotelDistributionRoomMapping(Document):
    def validate(self):
        connection_property = frappe.db.get_value("Hotel Distribution Connection", self.connection, "property")
        if connection_property != self.property:
            frappe.throw(_("Connection belongs to another property."))
        rt_property = frappe.db.get_value("Hotel Room Type", self.room_type, "property")
        if rt_property != self.property:
            frappe.throw(_("Room type belongs to another property."))
        if self.mapping_mode == "Room":
            if not self.room:
                frappe.throw(_("Exact Room is required for Room mapping mode."))
            room = frappe.db.get_value("Hotel Room", self.room, ["property", "room_type"], as_dict=True)
            if not room or room.property != self.property or room.room_type != self.room_type:
                frappe.throw(_("Mapped room must belong to this property and room type."))
        elif self.room:
            frappe.throw(_("Leave Exact Room empty for Room Type mapping mode."))
        if self.rate_plan and frappe.db.get_value("Hotel Rate Plan", self.rate_plan, "property") != self.property:
            frappe.throw(_("Rate plan belongs to another property."))
        duplicate = frappe.db.get_value(
            "Hotel Distribution Room Mapping",
            {"connection": self.connection, "external_room_id": self.external_room_id, "name": ("!=", self.name or "")},
            "name",
        )
        if duplicate:
            frappe.throw(_("External Room ID is already mapped on this connection."))
