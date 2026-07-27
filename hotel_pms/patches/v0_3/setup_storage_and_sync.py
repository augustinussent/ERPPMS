from hotel_pms.reconcile import backfill_legacy_invoice_links, backfill_sync_keys, reconcile_erpnext_links
from hotel_pms.setup_sync import setup_sync_fields


def execute() -> None:
    setup_sync_fields()
    backfill_legacy_invoice_links()
    backfill_sync_keys()
    reconcile_erpnext_links()
