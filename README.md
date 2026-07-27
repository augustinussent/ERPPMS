# Hotel PMS for ERPNext v16

Current starter release: **v0.2.0**

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
- Housekeeping tasks and before/after photos
- Maintenance tickets, preventive schedules, vendors, assets, costs, and prevention notes
- Group Booking lifecycle with tentative holds and automatic expiry
- Room blocks, cut-off release, rooming list, and participant reservation generation
- Meeting/function-space capacity and conflict control
- Halfday, fullday, fullboard, residential, wedding, and custom package templates
- ERPNext Quotation, Sales Order, Project, Group Folio, and multi-customer Sales Invoice integration
- BEO revision control, guaranteed/actual pax, package posting schedule, and group profitability report
- Printable/PDF Hotel Group Confirmation Letter

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
9. Assign hotel roles plus the corresponding ERPNext roles: Hotel Sales + Sales User/Manager, Front Desk, Banquet, Night Auditor, Housekeeping, Engineering, and Accounts User/Manager.

## Group meeting workflow

```text
Inquiry → Tentative Hold → Quotation → Confirmed Group Booking
       → Sales Order / Confirmation Letter / BEO
       → Rooming List / Participant Reservations
       → Package Schedule / Night Audit / Group Folio
       → Sales Invoice(s) / Payment / Profitability
```

Detailed setup and operating procedure: [`docs/GROUP_BOOKING.md`](docs/GROUP_BOOKING.md).

## Primary individual-stay workflow

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

## Production gaps to complete before go-live

This repository is a serious starter, not a finished replacement for OPERA, eZee, or other mature PMS products. Before production, implement and test:

- Availability tape chart and bulk room assignment
- Deposit and refund workflow using Payment Entry references
- Split folios and city ledger settlement
- Tax/service-charge rules for Indonesian operations
- Room moves, extensions, early departure, and group-room pickup reports
- No-show/cancellation fees
- Unified checkout payment across multiple ERPNext invoices
- Minibar stock issue workflow and physical reconciliation
- Audit log, shift closing, cash drawer, and night-audit close lock
- OTA/channel-manager integration and webhook retry queue
- Guest ID/privacy retention policies and access controls
- Automated backups, monitoring, restore drills, and disaster recovery
- Unit, integration, concurrency, and user-acceptance tests

## Upgrade an existing v0.1 site

```bash
cd ~/frappe-bench
bench get-app /path/to/hotel_pms_erpnext  # only when the app is not already installed
bench --site your-site.example migrate
bench build --app hotel_pms
bench restart
```

Migration creates the new DocTypes, ERPNext custom link fields, roles, report, scheduler jobs, and `Hotel Group Confirmation Letter` Print Format.

## Do not edit ERPNext core

All hotel-specific behavior belongs in this app. Use hooks, custom fields, document events, whitelisted methods, and patches. Core edits make upgrades expensive and turn future maintainers into amateur archaeologists.
