import frappe

def setup_production_gate():
    indexes={
      "Hotel Folio Charge":[["sales_invoice","is_already_invoiced","is_void"]],
      "Hotel Group Folio Charge":[["sales_invoice","is_already_invoiced","is_void"]],
      "Hotel City Ledger Charge":[["sales_invoice","is_already_invoiced","is_void"]],
      "Hotel Restaurant Bill Split":[["erpnext_document_type","erpnext_document","status"]],
      "Hotel Production Gate Run":[["property","status","environment_name"]],
    }
    for doctype,groups in indexes.items():
        if not frappe.db.exists("DocType",doctype): continue
        for fields in groups:
            try: frappe.db.add_index(doctype,fields)
            except Exception: pass
