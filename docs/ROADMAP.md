# Recommended Delivery Roadmap

## Completed foundation: v0.1.0-v0.3.0

- Native ERPNext master and accounting integration
- Reservation, folio, night audit, invoice, checkout, housekeeping task, maintenance, and preventive maintenance foundation
- Group bookings, room blocks, meeting packages, BEO, confirmation letter, group folio, and profitability
- Global photo-storage toggle
- ERPNext synchronization keys, sync ledger, per-charge invoice linkage, and conservative reconciliation

## Completed front-office release: v0.4.0

- Today dashboard and physical-room tape chart
- Quick multi-room booking, room move, extend stay, and early departure
- Guest Registration Card and occupants
- Cancellation/no-show policy and deposit/refund workflow

## Completed operations release: v0.5.0

- Mobile Housekeeping/Engineering operations and realtime notifications
- Priority queue, assignment, timer, checklist, inspection, and reclean
- Lost & Found, SLA, post-maintenance cleaning, Room History, KPI, and SOP Candidate

## Completed revenue and billing release: v0.6.0

- Rate plans, seasons, date calendar, derived rates, restrictions, floor approvals, and deterministic quote hash
- Vouchers and travel-agent contracts/commission settlements
- Configurable hotel tax and service-charge profiles mapped to ERPNext tax templates
- Folio split, transfer, reversal, unified checkout, and Payment Requests
- City ledger, direct-bill credit governance, and outstanding report
- Cashier shift, drawer movement, reconciliation, variance review, and reports

## Next release: v0.7.0 Guest-facing

- Direct booking engine
- Guest portal and secure self check-in
- Online payment and confirmation/cancellation portal
- Guest profile 360, duplicate merge, privacy retention, and anonymization

## v0.8.0 Restaurant and Guest Services

- Restaurant table map, KOT, kitchen display, split bills, QR ordering, and room service
- Guest laundry and experiences

## v0.9.0 Platform hardening

- Multi-property user scoping and consolidated dashboard
- Onboarding wizard and migration importers
- Versioned REST API, Postman/OpenAPI documentation, webhooks, and retry queues
- Full automated unit, integration, concurrency, permission, migration, and end-to-end test suite

## v1.0.0 production gate

- Accounting reconciliation has zero unexplained difference
- Reservation concurrency and duplicate-entry tests pass
- Backup and restore drill passes
- Role and privacy tests pass
- Department UAT is signed
- Parallel run is completed
- Operational SOP and training are complete
