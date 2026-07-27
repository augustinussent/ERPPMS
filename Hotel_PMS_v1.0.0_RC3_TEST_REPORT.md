# Hotel PMS ERPNext v1.0.0-rc3 Test Report

## Ruang lingkup

Pemeriksaan dilakukan terhadap source release candidate F&B Operational Depth. Environment build tidak memiliki bench Frappe/ERPNext v16 aktif, MariaDB, Redis, worker, atau Stock Ledger nyata.

## Hasil statis

| Pemeriksaan | Hasil |
|---|---:|
| Python parsed/compiled | 371 |
| JavaScript syntax | 57 |
| JSON parsed | 144 |
| DocType audited | 109 |
| Desk pages | 16 |
| Script/query reports | 11 |
| Property-scoped operational DocTypes | 67 |
| JavaScript-to-Python endpoint contracts | 24 |
| Pure-rule tests | 42 passed |
| DocType field-order errors | 0 |
| Property-scope errors | 0 |
| RC2 integration-contract errors | 0 |
| RC3 stock-contract errors | 0 |
| OpenAPI/Postman drift | 0 |

## Double-entry controls yang diperiksa

- Hanya `hotel_pms.fnb_inventory` yang boleh membuat ERPNext Stock Entry untuk recipe consumption.
- Pembuatan Stock Entry memakai `create_document_once()` dan `Hotel ERP Sync Log`.
- Stock Entry menggunakan unique `custom_hotel_sync_key`.
- Cancelled target memakai revision key melalui mekanisme sinkronisasi existing.
- Recipe Material Issue memaksa POS/Sales Invoice menggunakan `update_stock = 0`.
- ERPNext POS Finished Goods tidak menjalankan recipe Stock Entry.
- No Stock Posting tidak menjalankan kedua jalur stok.
- Satu KOT hanya menunjuk satu Stock Entry aktif.
- Order tidak dapat selesai jika recipe Stock Entry belum submitted atau Not Required.
- Cancel order setelah KOT fire tidak membuat stock reversal PMS.
- Cancel Stock Entry menandai Restaurant Order untuk rekonsiliasi.
- Production Gate memeriksa voucher Stock Ledger berdasarkan kebijakan outlet.

## Rule tests

Unit test mencakup:

- KDS status derivation.
- Partial-ready dan progress calculation.
- Mutually exclusive inventory paths.
- Recipe posting enablement.
- Recipe requirement aggregation.
- Seluruh rule tests Front Office, Guest, Housekeeping/Engineering, Revenue, Services, Platform, Production Gate, dan RC2 adoption.

## Belum dibuktikan

Wajib diuji pada staging ERPNext/Frappe v16:

1. Patch dan migrasi Custom Field Stock Entry.
2. `Material Issue` Stock Entry insert dan submit.
3. Stock UOM serta conversion factor pada item aktual.
4. Negative-stock behavior sesuai konfigurasi ERPNext.
5. Stock Ledger Entry setelah submit/cancel.
6. Revision-key repost setelah cancellation.
7. Concurrent KOT fire untuk ingredient yang sama.
8. Background worker restart saat posting berlangsung.
9. POS Profile tidak mengaktifkan stock update kembali pada recipe mode.
10. Sales Invoice room posting dan city ledger tetap `update_stock = 0`.
11. KDS realtime/websocket dan browser sound.
12. Menu CSV dengan data hotel aktual.
13. Backup dan isolated restore termasuk private files, Stock Entry, dan Stock Ledger.
14. Accounting serta stock reconciliation end-to-end.

## Status

**Static and rule-test pass. Staging candidate only.** Promotion ke v1.0.0 final tetap membutuhkan seluruh Production Gate dan sign-off departemen.
