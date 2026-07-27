import frappe

from hotel_pms.setup_intelligence import setup_intelligence


def execute():
    setup_intelligence()
    frappe.clear_cache()
    from hotel_pms.production_gate import _seed
    for name in frappe.get_all(
        "Hotel Production Gate Run",
        filters={"go_live_decision": ["in", ["", "Pending"]]},
        pluck="name",
    ):
        doc = frappe.get_doc("Hotel Production Gate Run", name)
        _seed(doc)
        doc.flags.production_gate_internal_update = True
        doc.save(ignore_permissions=True)
