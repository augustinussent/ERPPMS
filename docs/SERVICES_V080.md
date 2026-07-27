# Hotel PMS v0.8.0 — Restaurant & Guest Services

## Scope

- Outlet, dining area, table map, table reservation and QR token.
- Restaurant order, captain confirmation, KOT by kitchen station, kitchen display and daily KOT number.
- Item/quantity bill splits that must conserve the original order quantity.
- Draft ERPNext POS Invoice for direct settlement and draft ERPNext Sales Invoice for room/city-ledger posting.
- Laundry rate card, pickup, counted items, ready-by tracking, return and idempotent folio posting.
- Guest experiences with capacity control and folio posting.
- Cross-department shift handover.

## Accounting boundary

Restaurant orders, KOTs, laundry orders and experience bookings are operational records. Revenue, tax, stock and payment are posted only by ERPNext POS Invoice, Sales Invoice, Payment Entry and Stock Ledger.

## Go-live order

1. Configure outlets, POS Profiles, warehouses, cost centers, income accounts, tax profiles and walk-in customers.
2. Configure menu items and kitchen stations.
3. Configure restaurant tables and print the public QR URLs.
4. Run dine-in, room-service, split-bill and cancellation UAT.
5. Configure laundry rates and turnaround promises.
6. Configure guest experiences and capacity.
7. Train shift handover and escalation.
8. Reconcile every submitted invoice against order splits and ERPNext GL before production.
