# Hotel PMS ERPNext v1.0.0-rc8 Release Notes

## Distribution & Turnover Pack

RC8 adopts the latest useful patterns from Kamra PMS 2.3.0 and RentTools.io while preserving ERPNext as the only financial and stock source of truth.

### Added

- Provider-neutral channel-manager core.
- HMAC-signed Generic JSON inbound bookings.
- Secure Generic iCal import/export and distribution conflict detection.
- Property-scoped room/rate mappings and external-reference idempotency.
- ARI snapshot and adapter contracts.
- Controlled check-in readiness and room recommendation flow.
- One-time multilingual pre-arrival forms.
- Occupant ID private-file capture and retention purge.
- Turnover window and cleaner-conflict planner.
- Production Gate checks for distribution, pre-arrival security, and turnover.
- Frappe Cloud-compatible Python 3.10 floor with Frappe/ERPNext v16 declarations.

### Provider status

```text
Generic iCal    Shipped
Generic JSON    Shipped
Channex         Adapter
STAAH           Adapter
AioSell         Adapter
Custom          Adapter
```

Adapter means the protocol boundary exists. It does not mean live certification exists.

### Accounting and stock safety

RC8 does not directly create:

```text
Sales Invoice
POS Invoice
Payment Entry
Journal Entry
Purchase Invoice
Stock Entry
```

Inbound sell prices are reservation snapshots. ERPNext tax templates, invoices, payments, receivables, GL, and Stock Ledger remain authoritative.

### Upgrade status

RC8 is a staging candidate. Real Frappe/ERPNext v16 migration, provider callbacks, concurrency, restore, rollback, and departmental sign-off remain required.
