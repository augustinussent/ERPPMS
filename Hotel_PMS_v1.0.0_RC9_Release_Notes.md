# Hotel PMS ERPNext v1.0.0-rc9 Release Notes

## Summary

RC9 is the Restaurant ERP Control release. It adapts mature restaurant workflow patterns from URY while preserving ERPNext as the sole source for accounting, payments, tax, and inventory.

## Added

- Hotel Cashier Shift bridge to ERPNext POS Opening Entry and POS Closing Entry.
- Hotel Kitchen Production Unit.
- Incremental Add, Reduce, and Modify KOT revisions.
- Production-unit move as cancellation on the old unit plus addition on the new unit.
- Table Cluster for multi-table operational orders.
- Multi-route Restaurant Print Job queue with retry and dead-letter handling.
- Restaurant operational alerts.
- Restaurant Control Desk page.
- Cashier discount threshold and manager approval.
- ERPNext UOM-aware fractional quantities.
- Three mandatory Production Gate controls.
- RC9 real-bench smoke script and integration tests.

## Changed

- Restaurant confirmation, kitchen synchronization, and direct billing can require an active ERPNext POS session.
- Restaurant billing performs pre-bill checks for kitchen synchronization, ticket status, stock failures, and print failures.
- Discount is applied through ERPNext invoice discount fields for both direct and deferred settlement.
- Existing menu kitchen stations are migrated to Production Units.

## Safety decisions

- No custom accounting, payment, tax, COGS, or stock ledger was added.
- Reduction and cancellation KOTs never auto-reverse Stock Entry.
- Financial bill merge was not introduced.
- Table Cluster affects seating only.
- Printer failure cannot roll back the ERPNext invoice or restaurant transaction.

## Superseded candidate

RC8 is superseded because RC9 changes executable source and database schema. RC8 Production Gate evidence cannot be reused for RC9.
