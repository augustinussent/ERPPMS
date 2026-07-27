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

Open `/app/hotel-front-desk` for Front Office and `/app/hotel-housekeeping-mobile` for Housekeeping/Engineering mobile operations. Before using cancellation, no-show, deposit, or refund actions, configure a cancellation policy, fee Item, and ERPNext Mode of Payment accounts. Configure checklist templates and SLA values before enabling strict operational enforcement. See `docs/FRONT_OFFICE_V040.md` and `docs/OPERATIONS_V050.md`.

## Production gaps to complete before go-live

This repository is a serious starter, not a finished replacement for OPERA, eZee, or other mature PMS products. Before production, implement and test:

- Split folios, charge transfers, city ledger settlement, and unified checkout across multiple invoices
- Cashier shift, cash drawer, and night-audit close lock
- Tax/service-charge rules for Indonesian operations
- Rate calendar, derived rates, restrictions, vouchers, and travel-agent commissions
- Minibar stock issue workflow and physical reconciliation
- OTA/channel-manager integration and webhook retry queue
- Booking engine, guest portal, and online payment
- Privacy retention, anonymization, and access-control tests
- Automated backups, monitoring, restore drills, and disaster recovery
- Full bench-based unit, integration, concurrency, permission, migration, and user-acceptance tests

## Do not edit ERPNext core

All hotel-specific behavior belongs in this app. Use hooks, custom fields, document events, whitelisted methods, and patches. Core edits make upgrades expensive and turn future maintainers into amateur archaeologists.
