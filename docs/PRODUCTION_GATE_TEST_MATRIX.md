# v1.0 Production Gate Test Matrix

## Installation and migration
- Blank Frappe/ERPNext site installation.
- Upgrade rehearsal from an actual v0.9.0 database copy.
- Repeated `migrate` execution without duplicate custom fields, indexes, or master records.
- Worker, scheduler, Redis, websocket, email, payment gateway, and reverse-proxy smoke tests.

## Concurrency
- Last physical room.
- Last room-type inventory after group block.
- Same restaurant table.
- Last experience capacity.
- Duplicate payment callback and repeated idempotency key.
- Night audit and invoice creation under concurrent retry.

## Accounting and inventory
- Folio to submitted Sales Invoice.
- Deposit/refund to submitted Payment Entry.
- Restaurant split to POS/Sales Invoice and Stock Ledger.
- Travel-agent settlement to Purchase Invoice.
- City-ledger aging and credit exposure.
- Cashier expected versus counted cash.
- Tax and service-charge mapping reviewed by Finance.

## Security
- Cross-property IDOR through list, form, report, API, guest token, webhook, and migration records.
- CSRF, XSS, upload policy, token expiry, brute-force/rate limit, SSRF, session fixation, and secret rotation.
- Dependency and container scanning plus manual penetration test.

## Reliability and operations
- Full database/public/private files restore on an isolated host.
- Measured RPO/RTO.
- Rollback to the prior pinned image and backup.
- Department UAT, training, parallel run, escalation, support roster, and cutover approval.
