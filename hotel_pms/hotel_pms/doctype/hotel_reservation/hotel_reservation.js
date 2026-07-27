frappe.ui.form.on("Hotel Reservation", {
  refresh(frm) {
    if (frm.doc.docstatus === 1 && ["Confirmed", "Tentative"].includes(frm.doc.status)) {
      frm.add_custom_button(__("Check In"), () => run("hotel_pms.api.check_in", { reservation: frm.doc.name }), __("Operations"));
      frm.add_custom_button(__("Cancel Reservation"), () => cancellationDialog(frm, "Cancellation"), __("Operations"));
      frm.add_custom_button(__("Mark No Show"), () => cancellationDialog(frm, "No Show"), __("Operations"));
    }
    if (frm.doc.docstatus === 1 && frm.doc.status === "Checked In") {
      frm.add_custom_button(__("Check Out"), () => run("hotel_pms.api.check_out", { reservation: frm.doc.name }), __("Operations"));
      frm.add_custom_button(__("Move Room"), () => roomMoveDialog(frm), __("Stay Changes"));
      frm.add_custom_button(__("Extend / Early Departure"), () => stayAmendDialog(frm), __("Stay Changes"));
    }
    if (frm.doc.docstatus === 1 && !["Cancelled", "No Show"].includes(frm.doc.status)) {
      frm.add_custom_button(__("Registration Card"), async () => {
        const response = await frappe.call({ method:"hotel_pms.front_desk.ensure_guest_registration", args:{reservation:frm.doc.name}, freeze:true });
        frappe.set_route("Form", "Hotel Guest Registration", response.message.registration);
      }, __("Guest"));
      frm.add_custom_button(__("Record Deposit"), () => paymentDialog(frm, "Deposit"), __("Payments"));
      const canRefund = ["System Manager", "Hotel Manager", "Accounts User", "Accounts Manager"].some(role => frappe.user_roles.includes(role));
      if (canRefund && (frm.doc.deposit_received || 0) - (frm.doc.deposit_refunded || 0) > 0) {
        frm.add_custom_button(__("Create Refund"), () => paymentDialog(frm, "Refund"), __("Payments"));
      }
    }
    if (frm.doc.folio) frm.add_custom_button(__("Open Folio"), () => frappe.set_route("Form", "Hotel Folio", frm.doc.folio));
    if (frm.doc.registration) frm.add_custom_button(__("Open Registration"), () => frappe.set_route("Form", "Hotel Guest Registration", frm.doc.registration));
  },
});

async function run(method, args) { await frappe.call({ method, args, freeze:true }); cur_frm.reload_doc(); }

async function cancellationDialog(frm, type) {
  const preview = await frappe.call({ method:"hotel_pms.front_desk.preview_cancellation", args:{reservation:frm.doc.name,transaction_type:type} });
  const p = preview.message;
  const dialog = new frappe.ui.Dialog({ title:__(type), fields:[
    {fieldname:"preview",fieldtype:"HTML",options:`<div class="alert alert-warning">${__("Calculated fee")}: <b>${format_currency(p.fee_amount)}</b><br>${__("Net deposit")}: ${format_currency(p.deposit_received)}<br>${__("Estimated refund due")}: ${format_currency(p.refundable_amount)}</div>`},
    {fieldname:"reason",label:__("Reason"),fieldtype:"Small Text",reqd:1},
    {fieldname:"waive_fee",label:__("Waive Fee"),fieldtype:"Check",default:0},
    {fieldname:"waiver_reason",label:__("Waiver Reason"),fieldtype:"Small Text",depends_on:"eval:doc.waive_fee"},
  ], primary_action_label:__("Confirm"), primary_action:async values=>{
    values.reservation=frm.doc.name; values.transaction_type=type; values.idempotency_key=`WEB-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    await frappe.call({method:"hotel_pms.front_desk.cancel_reservation",args:values,freeze:true}); dialog.hide(); frm.reload_doc();
  }}); dialog.show();
}

function roomMoveDialog(frm) {
  const rows = frm.doc.rooms || [];
  const dialog = new frappe.ui.Dialog({ title:__("Move Room"), fields:[
    {fieldname:"old_room",label:__("Current Room"),fieldtype:"Select",options:rows.map(x=>x.room).join("\n"),reqd:1},
    {fieldname:"new_room",label:__("New Room"),fieldtype:"Link",options:"Hotel Room",reqd:1,get_query:()=>({filters:{property:frm.doc.property,operational_status:"Available",enabled:1}})},
    {fieldname:"reason",label:__("Reason"),fieldtype:"Small Text",reqd:1},
  ], primary_action_label:__("Move"), primary_action:async values=>{
    values.reservation=frm.doc.name; values.idempotency_key=`WEB-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    await frappe.call({method:"hotel_pms.front_desk.move_room",args:values,freeze:true}); dialog.hide(); frm.reload_doc();
  }}); dialog.show();
}

function stayAmendDialog(frm) {
  const dialog = new frappe.ui.Dialog({ title:__("Amend Stay Dates"), fields:[
    {fieldname:"new_arrival_date",label:__("Arrival Date"),fieldtype:"Date",default:frm.doc.arrival_date,reqd:1,read_only:frm.doc.status==="Checked In"},
    {fieldname:"new_departure_date",label:__("Departure Date"),fieldtype:"Date",default:frm.doc.departure_date,reqd:1},
    {fieldname:"reason",label:__("Reason"),fieldtype:"Small Text",reqd:1},
  ], primary_action_label:__("Apply"), primary_action:async values=>{
    values.reservation=frm.doc.name; values.idempotency_key=`WEB-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    await frappe.call({method:"hotel_pms.front_desk.amend_stay",args:values,freeze:true}); dialog.hide(); frm.reload_doc();
  }}); dialog.show();
}

function paymentDialog(frm, type) {
  const net = (frm.doc.deposit_received||0)-(frm.doc.deposit_refunded||0);
  const dialog = new frappe.ui.Dialog({ title:__(type), fields:[
    {fieldname:"amount",label:__("Amount"),fieldtype:"Currency",default:type==="Refund"?net:frm.doc.required_deposit,reqd:1},
    {fieldname:"mode_of_payment",label:__("Mode of Payment"),fieldtype:"Link",options:"Mode of Payment",reqd:1},
    {fieldname:"reference_no",label:__("Reference No"),fieldtype:"Data"},
    {fieldname:"reference_date",label:__("Reference Date"),fieldtype:"Date",default:frappe.datetime.get_today()},
  ], primary_action_label:__("Create Draft Payment Entry"), primary_action:async values=>{
    values.reservation=frm.doc.name; values.idempotency_key=`WEB-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const method=type==="Deposit"?"hotel_pms.front_desk.create_deposit_payment_entry":"hotel_pms.front_desk.create_refund_payment_entry";
    const response=await frappe.call({method,args:values,freeze:true}); dialog.hide(); frappe.set_route("Form","Payment Entry",response.message.payment_entry);
  }}); dialog.show();
}
