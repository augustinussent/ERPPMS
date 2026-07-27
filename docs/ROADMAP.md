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

## Completed guest-facing release: v0.7.0

- Direct booking engine using the same inventory and pricing rules as Front Office
- Secure guest portal, self check-in, payment request, booking/cancellation confirmation, and privacy requests
- Guest Profile 360, duplicate merge, consent, retention, anonymization, and controlled blacklist

## Completed restaurant and guest-services release: v0.8.0

- Restaurant outlets, dining areas, tables, reservations, operational table states, and mobile-friendly POS console
- Restaurant orders, captain confirmation, KOT routing, kitchen display, bill request, quantity split, and ERPNext invoice creation
- Public table QR menu and ordering with captain confirmation and transaction locking
- Room service and room/city-ledger posting without duplicate revenue
- Guest laundry workflow, promised-ready SLA, docket, guest request, and folio posting
- Guest experiences with capacity control and folio posting
- Cross-department shift handover and carry-forward

## Next release: v0.9.0 Platform hardening

- Multi-property user scoping, property switcher, and consolidated manager dashboard
- Setup/onboarding wizard and guided master-data validation
- CSV migration wizard with mapping, dry run, duplicate detection, rollback batch, and source presets
- Versioned REST API, OpenAPI/Postman documentation, webhook signature, outbound queue, retry, and dead-letter handling
- Full bench-based unit, integration, accounting, concurrency, permission, migration, browser, and end-to-end tests
- Observability: error reporting, queue/worker health, disk and database alerts, audit-log review, and backup verification
- Security hardening, dependency scan, secret rotation, penetration testing, and privacy-access test suite
- Automated backup, restore verification, disaster-recovery runbook, and measured RPO/RTO
- Restaurant follow-up: multi-table merge/move, waiting list, stock-aware sellout, return/credit-note workflow, alcohol-aware routing, and offline/retry queue
- Guest-services follow-up: supplier-cost capture, transport dispatch, spa resource scheduling, and guest acknowledgment for laundry count/return

## v1.0.0 production gate

- Accounting reconciliation has zero unexplained material difference
- Reservation, restaurant, laundry, payment, and duplicate-entry concurrency tests pass
- Backup and restore drill passes
- Role, property-scope, guest-token, and privacy tests pass
- Department UAT is signed by Front Office, Housekeeping, Engineering, Sales/Banquet, Finance, Restaurant, Laundry, and Management
- Parallel run is completed
- Operational SOP, training, support, rollback, RPO, and RTO documentation are complete


## v0.9.0 Platform Hardening
Implemented property isolation, onboarding, migration dry run, API governance, webhook queue, observability, backup verification, and CI/security scaffolding. Remaining production gate is v1.0.0 validation on a real bench and operational environment.
