from pathlib import Path
import ast
import json
import sys

root = Path(__file__).resolve().parents[1]
errors = []

# Only the ERPNext inventory adapter may create Stock Entry.
for path in (root / "hotel_pms").rglob("*.py"):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"get_doc", "new_doc"} or not node.args:
            continue
        arg = node.args[0]
        creates_stock = False
        if isinstance(arg, ast.Constant) and arg.value == "Stock Entry" and node.func.attr == "new_doc":
            creates_stock = True
        if isinstance(arg, ast.Dict):
            for key, value in zip(arg.keys, arg.values):
                if isinstance(key, ast.Constant) and key.value == "doctype" and isinstance(value, ast.Constant) and value.value == "Stock Entry":
                    creates_stock = True
        if creates_stock and path.name != "fnb_inventory.py":
            errors.append(f"{path.relative_to(root)}: Stock Entry creation outside ERPNext inventory adapter")

services = (root / "hotel_pms/services.py").read_text()
for needle in (
    "invoice_stock_fields(outlet)",
    "queue_ticket_stock_posting(kot.name)",
    "accept_kitchen_ticket",
    "recall_kitchen_ticket",
):
    if needle not in services:
        errors.append(f"services.py missing contract: {needle}")

inventory = (root / "hotel_pms/fnb_inventory.py").read_text()
for needle in (
    "create_document_once(",
    "base_key=base_key",
    '"custom_hotel_kitchen_ticket": ticket_doc.name',
    '"purpose": "Material Issue"',
    "invoice_updates_stock",
):
    if needle not in inventory:
        errors.append(f"fnb_inventory.py missing contract: {needle}")

outlet = json.loads((root / "hotel_pms/hotel_pms/doctype/hotel_outlet/hotel_outlet.json").read_text())
fields = {f["fieldname"]: f for f in outlet["fields"]}
if "inventory_posting_policy" not in fields:
    errors.append("Hotel Outlet missing inventory posting policy")

stock_custom = (root / "hotel_pms/setup_fnb_depth.py").read_text()
if '"custom_hotel_sync_key"' not in stock_custom or '"unique":1' not in stock_custom:
    errors.append("Stock Entry sync key is not uniquely configured")

print({"rc3_contract_errors": len(errors), "single_stock_adapter": True})
if errors:
    print("\n".join(errors))
    sys.exit(1)
