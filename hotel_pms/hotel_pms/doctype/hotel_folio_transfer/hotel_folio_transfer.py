import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class HotelFolioTransfer(Document):
    def validate(self):
        self.total_transferred = sum(flt(row.transfer_amount) for row in self.lines)
        if self.source_folio_type == self.destination_folio_type and self.source_folio == self.destination_folio:
            frappe.throw(_("Source and destination folio must be different."))
    def before_cancel(self):
        frappe.throw(_("Applied folio transfers are reversed through the controlled reversal action, not cancelled directly."))
