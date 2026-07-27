# Hotel PMS ERPNext v0.8.0 — Test Report

Tanggal pemeriksaan: 21 Juli 2026  
Scope: static source validation dan pure-rule tests  
Platform target: Frappe Framework v16 dan ERPNext v16

## Ringkasan hasil

```text
Python files compiled              275
JavaScript files checked            47
JSON files validated               110
DocTypes audited                    90
JS/Python endpoint contracts        62
Pure-rule tests passed              25
Audit errors                         0
Audit warnings                       0
```

## Pemeriksaan yang dijalankan

### Python compilation

```bash
python -m compileall -q hotel_pms
```

Hasil: berhasil tanpa syntax error.

### JavaScript syntax

```bash
find hotel_pms -type f -name '*.js' -print0 | xargs -0 -n1 node --check
```

Hasil: 47 file lolos.

### Pure-rule tests

```bash
pytest -q hotel_pms/tests
```

Hasil:

```text
25 passed
```

Test meliputi aturan front desk, guest security/privacy, housekeeping/maintenance, revenue/tax/rate, restaurant allocation, table state, laundry overdue, dan experience capacity helper.

### JSON validation

Seluruh DocType, Page, Report, Workspace, dan fixture JSON diparsing dengan Python `json.loads`.

Hasil: 110 file valid.

### Application contract audit

Audit internal memeriksa:

- duplicate fieldname;
- field_order consistency;
- Link/Dynamic Link/Table options;
- child DocType controller presence;
- Python import/module presence;
- JavaScript call terhadap whitelisted Python method;
- Hotel PMS Settings field references;
- route/page/report structure;
- versioned patch registration.

Hasil:

```json
{
  "doctypes": 90,
  "python_modules": 275,
  "js_endpoints": 62,
  "errors": [],
  "warnings": []
}
```

## v0.8.0 invariants yang diperiksa secara source-level

- Restaurant table dan experience capacity memakai database row lock pada controlled create path.
- Restaurant order mempunyai deterministic request key.
- QR order token scoped ke satu table dan retry tidak membuat order kedua.
- Table hanya mempunyai satu active non-billed/non-cancelled order.
- KOT request key mencakup order, station, dan request.
- Bill split quantity harus tepat mengalokasikan source order quantity.
- Bill split tidak dapat melewati source quantity.
- Direct settlement membuat ERPNext POS Invoice, bukan ledger PMS baru.
- Room/city posting membuat ERPNext Sales Invoice dan linked operational lines.
- Restaurant order tidak dapat completed sebelum non-complimentary invoice submitted.
- Invoice cancellation membuka ulang Restaurant Order billing state.
- Complimentary creation/change membutuhkan manager authorization.
- Laundry dan experience folio posting memakai deterministic idempotency key.
- Shift carry-forward memakai deterministic key.
- Public image tetap mengikuti global photo policy.
- Status operasional utama dibuat read-only dan diubah melalui controlled method.

## Artefak lama yang diperbaiki

Dua child DocType lama yang sebelumnya tidak mempunyai controller stub sekarang memiliki controller:

- Hotel Booking Gallery Image;
- Hotel Cleaning Checklist Template Item.

Audit warning turun menjadi nol.

## Yang belum diuji dalam lingkungan ini

Pemeriksaan ini belum menggantikan staging ERPNext nyata. Hal berikut masih wajib diuji:

1. `bench migrate` dan patch v0.8.0.
2. ERPNext POS Profile dan POS Opening Entry.
3. POS Invoice/Sales Invoice submit, cancel, return, tax, GL, dan Stock Ledger.
4. Payment rows dan Cashier Shift reconciliation.
5. MariaDB concurrent QR/table/order/split/experience operations.
6. Redis, worker, scheduler, realtime/socket, dan notifications.
7. Public QR route melalui reverse proxy dan rate limiting.
8. Mobile/tablet browser behavior.
9. KOT thermal printer 80 mm.
10. Role and property permission matrix.
11. Room/city posting checkout reconciliation.
12. Laundry auto-post dan overdue scheduler.
13. Backup, restore, rollback, and disaster recovery.
14. End-to-end accounting and inventory reconciliation.

## Go-live verdict

**Static source gate: PASS.**  
**Production gate: NOT YET PASSED.**

Rilis harus dipasang pada staging ERPNext v16, diuji dengan data dan akun hotel, lalu melewati UAT Restaurant, Kitchen, Front Office, Laundry, Guest Services, Finance, dan Management sebelum produksi.
