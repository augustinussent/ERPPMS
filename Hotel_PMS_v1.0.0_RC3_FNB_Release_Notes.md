# Hotel PMS ERPNext v1.0.0-rc3

## F&B Operational Depth

### Ditambahkan

- Kitchen Display System v2 dengan accept/start, per-item progress, course, allergy alert, aging, late flag, recall, guest/captain context, sound, dan realtime update.
- Recipe per `Hotel Outlet Menu Item` menggunakan ERPNext stock Item dan Stock UOM.
- Satu idempotent ERPNext `Stock Entry` Material Issue per KOT.
- `Hotel ERP Sync Log` dan revision key untuk retry setelah Stock Entry dibatalkan.
- Kebijakan inventori outlet: finished goods, recipe material issue, atau tanpa posting stok.
- Menu dan recipe bulk import dengan dry-run preview.
- Restaurant Stock Reconciliation report.
- Production Gate yang memahami voucher stok berdasarkan kebijakan outlet.

### Pencegahan double entry

Pada mode Recipe Material Issue:

- POS Invoice dan Sales Invoice dibuat dengan `update_stock = 0`.
- Hanya Stock Entry KOT yang menggerakkan Stock Ledger.
- Restaurant Order tidak dapat selesai jika Stock Entry KOT belum submitted atau dinyatakan Not Required.
- Cancellation order setelah KOT fire tidak mengembalikan stok otomatis.
- Cancellation Stock Entry menandai order untuk rekonsiliasi dan tidak membuat reversal PMS.

Pada mode ERPNext POS Finished Goods:

- Invoice menggunakan `update_stock = 1`.
- Recipe Stock Entry tidak dibuat.

### Status rilis

Rilis ini tetap release candidate. Aktivasi Recipe Material Issue harus dilakukan di staging dan harus melewati Stock Ledger reconciliation, concurrency test, backup/restore, serta UAT F&B dan Finance.
