# Hotel PMS for ERPNext v16

Starter Property Management System built as a native Frappe app on top of ERPNext.

## Why this architecture

The PMS and ERPNext share one Frappe site and one database. Hotel documents remain in the `hotel_pms` app, while finance, stock, purchasing, assets, suppliers, users, and permissions remain in ERPNext. This avoids fragile duplicate-master synchronization.

## Included MVP

- Multi-property hotel master
- Room types, rooms, and ERPNext asset/warehouse mapping
- Rate plans
- Reservations with room-overlap validation
- Check-in and check-out room status transitions
- Guest and corporate billing through ERPNext `Customer`
- Guest folio and item-based charges
- Idempotent night audit room-charge posting
- Sales Invoice generation from uninvoiced folio charges
- POS Invoice mirroring into the folio without duplicating revenue
- Mobile Housekeeping queue with priority, assignment, timer, checklist, supervisor inspection, and reclean
- Lost & Found with chain of custody
- Maintenance tickets with FO/HK intake, SLA, room blocks, post-maintenance cleaning, preventive schedules, vendors, assets, costs, and prevention notes
- Unified Room History, Housekeeping KPI, Maintenance SLA, and SOP Candidate
- Front Desk dashboard and physical-room tape chart
- Idempotent quick multi-room booking
- Controlled room move, extend stay, and early departure with change logs
- Cancellation/no-show policies and confirmation print format
- Guest Registration Card and registered occupants
- ERPNext Payment Entry drafts for deposits and refunds
- Deterministic rate calendar, seasons, derived plans, restrictions, floor-rate approvals, and quote hashes
- Voucher redemption and travel-agent commission settlement
- Configurable hotel tax/service-charge profiles mapped to ERPNext tax templates
- Folio split, transfer, reversal, unified checkout, Payment Request links, and city ledger
- Cashier shifts, drawer movements, ERPNext cash/POS reconciliation, and variance review
- Direct booking engine and secure guest portal using hashed expiring tokens
- Self check-in, guest cancellation, online Payment Request, and booking confirmation
- Guest Profile 360, consent ledger, duplicate merge workflow, privacy requests, anonymization, and controlled blacklist

## Important accounting rule

A folio is an operational subledger, not the ERPNext general ledger. Uninvoiced room and service charges become an ERPNext Sales Invoice. A submitted POS Invoice has already posted revenue, tax, stock, and receivables, so the PMS mirrors it into the folio as `Already Invoiced` and excludes it from the checkout Sales Invoice.

## Prerequisites

- Frappe Framework 16
- ERPNext 16
- Python 3.14+
- Node.js 24+
- MariaDB/Redis and the remaining dependencies required by Frappe v16

## Install in a bench

```bash
cd ~/frappe-bench
bench get-app /path/to/hotel_pms_erpnext
bench --site your-site.example install-app hotel_pms
bench --site your-site.example migrate
bench build --app hotel_pms
bench restart
```

For GitHub usage:

```bash
bench get-app https://github.com/YOUR-ORG/hotel_pms.git --branch main
bench --site your-site.example install-app hotel_pms
```

## First configuration

1. Configure ERPNext Company, chart of accounts, cost centers, warehouses, customers, items, price lists, taxes, modes of payment, suppliers, and assets.
2. Create a `Hotel Property` linked to the ERPNext Company.
3. Create non-stock service Items such as Room Revenue, Breakfast, Laundry, Late Checkout, and Transport.
4. Create stock Items for minibar and amenities where stock control is required.
5. Create room types and map each room type to its Room Revenue Item.
6. Create rooms. Optionally map each room to an ERPNext Asset and a room/minibar Warehouse.
7. Create rate plans.
8. Configure `Hotel PMS Settings` and leave overbooking disabled during rollout.
9. Assign roles: Hotel Manager, Front Desk, Night Auditor, Housekeeping, Housekeeping Supervisor, Engineering, Engineering Supervisor, and ERPNext Accounts roles where financially required.
10. Configure cleaning checklist templates and Engineering SLA values before enabling enforcement.

## Primary workflow

```text
Customer / Contact
        ↓
Hotel Reservation → Check-in → Open Folio
        ↓                         ↓
Room inventory               Night Audit / Service Charges
                                  ↓
                              Sales Invoice
                                  ↓
                         Payment Entry / Receivable
        ↓
Check-out → Room Dirty → Housekeeping → Clean / Inspected
```

## Front Desk and Operations

Open `/app/hotel-front-desk` for Front Office, `/app/hotel-housekeeping-mobile` for Housekeeping/Engineering, `/app/hotel-revenue-calendar` for Revenue, `/app/hotel-checkout` for billing, and `/app/hotel-cashier` for cashier operations. Configure cancellation policy, Mode of Payment accounts, tax profile, rate plans, voucher-discount Item, credit accounts, and checklist/SLA values before enabling strict controls. See `docs/FRONT_OFFICE_V040.md`, `docs/OPERATIONS_V050.md`, and `docs/REVENUE_BILLING_V060.md`.

## Production gaps to complete before go-live

This repository is a serious starter, not a finished replacement for OPERA, eZee, or other mature PMS products. Before production, implement and test:

- Night-audit business-date lock and formal cashier handover approval
- Accountant-approved Indonesian tax/service-charge setup and regulatory reporting
- OTA/channel-manager rate and inventory distribution
- Revenue forecasting and automated pricing recommendations
- Minibar and restaurant stock issue workflow with physical reconciliation
- Property-scope, privacy, and guest-token access-control tests
- Automated backups, monitoring, restore drills, and disaster recovery
- Full bench-based unit, integration, concurrency, permission, migration, and user-acceptance tests

## Do not edit ERPNext core

All hotel-specific behavior belongs in this app. Use hooks, custom fields, document events, whitelisted methods, and patches. Core edits make upgrades expensive and turn future maintainers into amateur archaeologists.


### Public booking deposit
The required deposit percentage is configured only in **Hotel PMS Settings → Public Booking Deposit Percent**. The public API never accepts a guest-supplied deposit percentage.


## v0.8.0 Restaurant & Guest Services

Operational pages:

```text
/app/hotel-restaurant-pos
/app/hotel-kitchen-display
/app/hotel-laundry-desk
/app/hotel-shift-handover
/hotel-dine#table=<qr-token>
```

The release adds outlet/table operations, KOT and kitchen display, controlled split billing to ERPNext POS/Sales Invoice, QR ordering, room service, laundry, experiences, and shift handover. See `docs/SERVICES_V080.md`.


## v1.0.0-rc1 Platform Hardening

Use `/app/hotel-platform-console`, `/app/hotel-onboarding`, and `/app/hotel-migration-importer`. Assign every operational user through `Hotel User Property Access`. API v1 documentation is in `docs/openapi-v1.json`. See `docs/PLATFORM_HARDENING_V090.md`.


## Production approval
Open `/app/hotel-production-gate`. This release remains a candidate until a specific environment passes all mandatory checks and departmental sign-offs.

## v1.0.0-rc2 Localization & Communication

Rilis ini menambahkan country-pack Indonesia, validasi pemetaan pajak ke ERPNext, WhatsApp Meta Cloud API yang asynchronous dan idempotent, communication inbox, serta private guest-document pipeline. Halaman operasional tersedia pada:

```text
/app/hotel-communications
```

ERPNext tetap menjadi satu-satunya sumber transaksi keuangan dan stok. Modul localization, komunikasi, dan dokumen tamu tidak membuat Sales Invoice, POS Invoice, Payment Entry, Journal Entry, Purchase Invoice, atau Stock Entry. Rincian implementasi terdapat di `docs/ADOPTION_V100_RC2.md`.

## v1.0.0-rc4 Production Validation Pack

RC4 freezes the exact source and container identity in a Release Manifest, records immutable environment rehearsals, imports parallel-run reconciliation evidence, and blocks release promotion until the Production Gate is Approved with a Go decision. The module is evidence-only: it does not create Sales Invoice, POS Invoice, Payment Entry, Journal Entry, Purchase Invoice, or Stock Entry documents.

Operational page: `/app/hotel-production-gate`.

## v1.0.0-rc3 F&B Operational Depth

Operational pages:

```text
/app/hotel-kitchen-display
/app/hotel-menu-import
/app/query-report/Hotel Restaurant Stock Reconciliation
```

Outlet inventory policy is mutually exclusive: ERPNext POS finished goods, recipe Material Issue, or no stock posting. Recipe mode creates one idempotent ERPNext Stock Entry per KOT and forces restaurant invoices to `update_stock = 0`. See `docs/FNB_DEPTH_V100_RC3.md`.

## v1.0.0-rc5 staging execution

RC5 adds an executable staging-validation layer over the RC4 Production Gate. From a Frappe v16 bench, run:

```bash
BENCH_ROOT="$HOME/frappe-bench" \
SITE="staging.example.com" \
GATE_RUN="HPG-2026-00001" \
apps/hotel_pms/ci/run_staging_execution.sh
```

The command backs up the staging site, migrates it, captures preflight and smoke evidence, reads accounting/stock reconciliation, builds a private cutover bundle, and verifies every generated evidence file by SHA-256. It does not create Sales Invoice, POS Invoice, Payment Entry, Journal Entry, Purchase Invoice, or Stock Entry.


## v1.0.0-rc6 Intelligence & Control
Governed decision records, night-audit anomaly findings, ERPNext-native payment correction control, honest integration registry, and expanded real-bench smoke tooling. No parallel accounting or stock ledger is introduced.


## v1.0.0-rc7 Control Hotfix

RC7 supersedes RC6 for staging validation. It fixes payment-refund caps, integration lifecycle/readiness blockers, unresolved correction gating, and blank parallel-run input. ERPNext remains the single financial and stock source of truth.

## v1.0.0-rc8 Distribution & Turnover

RC8 supersedes RC7 because executable source changed. It adds an ERPNext-safe distribution seam, secure Generic iCal fallback, HMAC-signed Generic JSON inbound bookings, controlled check-in context, one-time pre-arrival forms, and turnover planning.

Operational pages:

```text
/app/hotel-distribution-console
/app/hotel-turnover-planner
/hotel-prearrival?token=<one-time-token>
```

Provider maturity is explicit:

- **Generic iCal:** Shipped. Import/export only, exact-room inventory blocks, no guest or financial posting.
- **Generic JSON:** Shipped. HMAC-signed normalized booking webhook through the same Hotel Reservation validation path.
- **Channex, STAAH, AioSell:** Adapter. Protocol seam and configuration are present, but Live is blocked until credentials, mapping, certification, and staging evidence exist.

Inbound distribution creates Hotel Reservation operational records only. ERPNext remains the sole source for Sales Invoice, Payment Entry, Accounts Receivable, taxes, General Ledger, Stock Entry, and Stock Ledger. See `docs/DISTRIBUTION_TURNOVER_V100_RC8.md`.
## v1.0.0-rc9 Restaurant ERP Control

RC9 deepens the restaurant workflow while keeping ERPNext authoritative:

- Hotel Cashier Shift is bridged to submitted ERPNext POS Opening Entry and POS Closing Entry.
- Restaurant quantities follow ERPNext UOM whole-number rules and support three-decimal weighed quantities.
- Kitchen changes are emitted as idempotent Add, Reduce, or Modify KOT revisions per production unit.
- Only Add deltas may create ERPNext recipe Material Issue Stock Entries; cancellation does not auto-reverse stock.
- Cashier discounts are approved against an outlet threshold and posted through ERPNext POS/Sales Invoice discount fields.
- Table clusters, durable multi-printer jobs, operational alerts, and a Restaurant Control console are included.
- Production Gate blocks unresolved POS-session, kitchen-delta, and print-queue problems.

See `docs/RESTAURANT_ERP_CONTROL_V100_RC9.md`.
