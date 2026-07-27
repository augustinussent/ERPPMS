import frappe


def execute():
    """Refresh metadata and seed new RC5 gate checks on open gate runs."""
    frappe.clear_cache()
    for name in frappe.get_all(
        "Hotel Production Gate Run",
        filters={"go_live_decision": ["in", ["", "Pending"]]},
        pluck="name",
    ):
        doc = frappe.get_doc("Hotel Production Gate Run", name)
        from hotel_pms.production_gate import _seed

        _seed(doc)
        doc.flags.production_gate_internal_update = True
        doc.save(ignore_permissions=True)
