from frappe.model.document import Document
from frappe import _
import frappe
from frappe.utils import getdate


class HotelRateCalendar(Document):
    def autoname(self):
        self._set_calendar_key()
        self.name = self.calendar_key

    def validate(self):
        if not self.property or not self.room_type or not self.rate_plan or not self.rate_date:
            frappe.throw(_("Property, room type, rate plan, and date are required."))
        plan = frappe.db.get_value("Hotel Rate Plan", self.rate_plan, ["property", "room_type"], as_dict=True)
        if not plan or plan.property != self.property or plan.room_type != self.room_type:
            frappe.throw(_("Rate plan scope does not match the calendar row."))
        self._set_calendar_key()
        if self.maximum_stay and self.minimum_stay and self.maximum_stay < self.minimum_stay:
            frappe.throw(_("Maximum stay cannot be below minimum stay."))

    def _set_calendar_key(self):
        if self.property and self.room_type and self.rate_plan and self.rate_date:
            self.calendar_key = f"{self.property}|{self.room_type}|{self.rate_plan}|{getdate(self.rate_date)}"
