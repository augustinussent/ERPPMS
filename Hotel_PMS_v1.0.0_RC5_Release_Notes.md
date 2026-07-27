# Hotel PMS ERPNext v1.0.0-rc5 Release Notes

## Ringkasan

RC5 menambahkan Staging Execution Pack di atas Production Validation RC4.

## Tambahan

- Staging environment preflight.
- Smoke rehearsal read-only.
- Immutable reconciliation snapshot.
- Duplicate active ERP sync-key detection.
- Private cutover bundle.
- Filesystem evidence manifest dan verifier.
- Tombol baru pada halaman Hotel Production Gate.
- Script orkestrasi staging untuk bench Frappe v16.

## Accounting boundary

Modul RC5 tidak membuat Sales Invoice, POS Invoice, Payment Entry, Journal Entry, Purchase Invoice, atau Stock Entry. Semua nilai keuangan dan stok dibaca dari ERPNext.

## Status

Staging candidate. Promosi ke v1.0.0 final tetap membutuhkan eksekusi nyata, parallel run, restore/rollback, security/performance test, dan sign-off seluruh departemen.

## Source fingerprint

```text
098c93c8992d71ccbcbcbc11bc3472028cf30db14b825b5edb5978e75d09a5eb
```
