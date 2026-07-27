frappe.ui.form.on("Payment Entry", {
  refresh(frm) {
    if (frm.is_new() || !frappe.model.can_create("Hotel Payment Correction")) return;
    frm.add_custom_button(__("Correct Payment"), async () => {
      const r = await frappe.call({
        method: "hotel_pms.intelligence.preview_payment_correction",
        args: { payment_entry: frm.doc.name },
        freeze: true,
      });
      const p = r.message || {};
      const actions = p.allowed_actions || [];
      const d = new frappe.ui.Dialog({
        title: __("Governed Payment Correction"),
        fields: [
          {fieldname:"summary",fieldtype:"HTML",options:`<div class="alert alert-info">${frappe.utils.escape_html(p.reason||"")}<br>${__("Maximum refundable")}: ${format_currency(p.maximum_refundable||0, frm.doc.paid_to_account_currency || frm.doc.paid_from_account_currency)}</div>`},
          {fieldname:"requested_action",label:__("Action"),fieldtype:"Select",options:actions.join("\n"),reqd:1,default:actions[0]},
          {fieldname:"amount",label:__("Amount"),fieldtype:"Currency",default:p.maximum_refundable||0,depends_on:"eval:doc.requested_action==='Create Refund'"},
          {fieldname:"mode_of_payment",label:__("Mode of Payment"),fieldtype:"Link",options:"Mode of Payment",default:p.mode_of_payment,depends_on:"eval:doc.requested_action==='Create Refund'"},
          {fieldname:"reason",label:__("Reason"),fieldtype:"Small Text",reqd:1},
        ],
        primary_action_label: __("Create Approval Request"),
        primary_action: async values => {
          const doc = await frappe.db.insert({
            doctype:"Hotel Payment Correction",
            property:p.property,
            payment_entry:frm.doc.name,
            reservation:p.reservation,
            requested_action:values.requested_action,
            amount:values.amount,
            mode_of_payment:values.mode_of_payment,
            reason:values.reason,
          });
          d.hide();
          frappe.set_route("Form","Hotel Payment Correction",doc.name);
        }
      });
      d.show();
    }, __("Hotel PMS"));
  }
});
