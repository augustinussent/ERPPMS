from frappe.model.document import Document
import frappe

class HotelProductionGateRun(Document):
    def before_save(self):
        if self.is_new() or self.flags.get("production_gate_internal_update"):
            return
        old=self.get_doc_before_save()
        if not old:
            return
        protected=("status","blocker_count","warning_count","passed_count","measured_rpo_minutes","measured_rto_minutes","go_live_decision","decision_by","decision_at","actual_frappe_version","actual_erpnext_version","actual_image_digest")
        if any(self.get(f)!=old.get(f) for f in protected):
            frappe.throw("Production gate results and decision must be changed through controlled actions.",frappe.PermissionError)
        def snapshot(doc,table,fields):
            return [(r.name,)+tuple(r.get(f) for f in fields) for r in doc.get(table)]
        cf=("check_code","status","measured_value","threshold","details","evidence_url","checked_at","checked_by")
        sf=("department","approver","status","signed_at","comments")
        if snapshot(self,"checks",cf)!=snapshot(old,"checks",cf) or snapshot(self,"signoffs",sf)!=snapshot(old,"signoffs",sf):
            frappe.throw("Production gate evidence and sign-offs must be changed through controlled actions.",frappe.PermissionError)
