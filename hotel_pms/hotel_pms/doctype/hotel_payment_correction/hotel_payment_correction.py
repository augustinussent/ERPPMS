import json
import frappe
from frappe import _
from frappe.model.document import Document
from hotel_pms.intelligence_rules import payment_correction_plan

class HotelPaymentCorrection(Document):
    def validate(self):
        if not self.payment_entry: return
        pe=frappe.get_doc("Payment Entry",self.payment_entry)
        reservation=getattr(pe,"custom_hotel_reservation",None)
        self.reservation=reservation
        if reservation:
            self.property=frappe.db.get_value("Hotel Reservation",reservation,"property")
        elif getattr(pe,"custom_hotel_cashier_shift",None):
            self.property=frappe.db.get_value("Hotel Cashier Shift",pe.custom_hotel_cashier_shift,"property")
        if not self.property:
            frappe.throw(_("Property cannot be derived from this Payment Entry. Link it to a Hotel Reservation or Hotel Cashier Shift before requesting correction."))
        original_amount=float(pe.paid_amount or pe.received_amount or 0)
        refundable=0.0
        if reservation:
            from hotel_pms.front_desk import get_deposit_summary
            refundable=float(get_deposit_summary(reservation).get("net_deposit") or 0)
        plan=payment_correction_plan(
            docstatus=int(pe.docstatus or 0), payment_type=pe.payment_type,
            hotel_transaction_type=getattr(pe,"custom_hotel_transaction_type",None),
            original_amount=original_amount, refundable_amount=refundable,
        )
        self.original_docstatus=pe.docstatus
        self.original_payment_type=pe.payment_type
        self.original_transaction_type=getattr(pe,"custom_hotel_transaction_type",None)
        self.original_amount=original_amount
        self.refundable_amount=refundable
        self.allowed_actions_json=json.dumps(plan,sort_keys=True)
        if self.requested_action not in plan["allowed_actions"]:
            frappe.throw(_("Requested action is not legal for the current Payment Entry state."))
        if self.requested_action == "Create Refund":
            if not self.reservation: frappe.throw(_("Only hotel-linked Payment Entries can use the governed refund action."))
            if float(self.amount or 0)<=0 or float(self.amount or 0)>refundable:
                frappe.throw(_("Refund amount must be greater than zero and cannot exceed the refundable balance."))
            if not self.mode_of_payment: frappe.throw(_("Mode of Payment is required for a refund."))
        if not self.idempotency_key:
            self.idempotency_key=frappe.generate_hash(length=24)
        if self.is_new():
            self.requested_by=frappe.session.user
            self.requested_at=frappe.utils.now_datetime()
            self.status="Pending Approval"
        active=frappe.db.get_value(self.doctype,{"payment_entry":self.payment_entry,"status":["in",["Pending Approval","Approved"]],"name":["!=",self.name]},"name")
        if active: frappe.throw(_("An active correction request already exists for this Payment Entry."))
