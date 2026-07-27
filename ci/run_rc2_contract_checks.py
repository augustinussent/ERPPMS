from pathlib import Path
import ast
import sys

root = Path(__file__).resolve().parents[1]
errors = []
financial = {
    "Sales Invoice",
    "POS Invoice",
    "Payment Entry",
    "Journal Entry",
    "Purchase Invoice",
    "Stock Entry",
}
new_modules = (
    "hotel_pms/communications.py",
    "hotel_pms/media.py",
    "hotel_pms/localization/registry.py",
    "hotel_pms/localization/indonesia.py",
)

for rel in new_modules:
    path = root / rel
    text = path.read_text()
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Detect frappe.new_doc("Sales Invoice") and similar calls.
        if isinstance(node.func, ast.Attribute) and node.func.attr == "new_doc" and node.args:
            value = node.args[0]
            if isinstance(value, ast.Constant) and value.value in financial:
                errors.append(f"{rel}: forbidden financial document creation {value.value}")
        # Detect literal frappe.get_doc({"doctype": "Sales Invoice", ...}).
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get_doc" and node.args:
            value = node.args[0]
            if isinstance(value, ast.Dict):
                pairs = {
                    k.value: v.value
                    for k, v in zip(value.keys, value.values)
                    if isinstance(k, ast.Constant) and isinstance(v, ast.Constant)
                }
                if pairs.get("doctype") in financial:
                    errors.append(f"{rel}: forbidden financial document creation {pairs['doctype']}")
    if 'append("taxes"' in text or "append('taxes'" in text:
        errors.append(f"{rel}: localization/communication module may not append ERPNext tax rows")

required_contracts = {
    "hotel_pms/api/__init__.py": "resolve_invoice_tax_context",
    "hotel_pms/billing.py": "resolve_invoice_tax_context",
    "hotel_pms/group_booking.py": "by_customer_and_profile",
    "hotel_pms/communications.py": 'frappe.enqueue("hotel_pms.communications.send_queued_message"',
    "hotel_pms/media.py": "is_private=1",
}
for rel, needle in required_contracts.items():
    if needle not in (root / rel).read_text():
        errors.append(f"{rel}: missing v1.0.0-rc2 integration contract {needle}")

print({"rc2_contract_errors": len(errors), "guarded_financial_doctypes": len(financial)})
if errors:
    print("\n".join(errors))
    sys.exit(1)
