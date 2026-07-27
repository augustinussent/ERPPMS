# Recommended Delivery Roadmap

## Phase 1: Foundation and staging

- Deploy ERPNext v16 and this custom app on a staging site
- Configure Company, Cost Centers, Warehouses, Items, Taxes, Customers, Suppliers, and Assets
- Import room and rate masters
- Test reservation conflict handling and roles

## Phase 2: Front office MVP

- Reservation, check-in, room status, folio, night audit, invoice, and checkout
- Arrival/departure/in-house dashboards
- Deposit and refund workflow
- Print formats for registration card, folio, and invoice

## Phase 3: Housekeeping and engineering

- Mobile-friendly room board
- Housekeeping productivity and inspection
- Maintenance SLA, before/after evidence, root cause, and recurrence prevention
- Calendar- and meter-based preventive maintenance

## Phase 4: Revenue and integrations

Implemented in v0.2 starter:

- Group bookings, room blocks, meeting spaces, package templates, BEO revisions, confirmation letters, group folios, package posting, and profitability

Remaining:

- Rate calendar, promo codes, corporate contracts
- Website booking engine
- Channel manager/OTA API integration with retry and reconciliation
- Restaurant/POS room-charge settlement

## Phase 5: Production hardening

- Concurrency tests, audit tests, role tests, backup/restore drills
- Monitoring, error reporting, queue monitoring, and database tuning
- Parallel run, migration reconciliation, SOP training, and phased go-live
