# Hotel PMS v1.0.0-rc9: Restaurant ERP Control

RC9 adapts the strongest operational patterns found in URY while retaining the Hotel PMS domain model and ERPNext as the financial and stock system of record.

## Design boundary

Hotel Restaurant Order, Kitchen Ticket, Table Cluster, Print Job, and Restaurant Alert are operational records. They cannot replace or independently post:

- ERPNext POS Opening Entry and POS Closing Entry
- POS Invoice and Sales Invoice
- Payment Entry
- Sales Taxes and Charges
- Stock Entry and Stock Ledger Entry
- General Ledger and Accounts Receivable

## Cashier session bridge

An outlet may require a submitted ERPNext POS Opening Entry. In that mode, restaurant order confirmation, KOT synchronization, pre-bill checks, and direct settlement require an Open Hotel Cashier Shift linked to the matching ERPNext opening document.

The company, POS Profile, user, outlet, and property must agree. A shift cannot close when the outlet requires ERPNext session control until a submitted Closed POS Closing Entry is linked.

## Incremental KOT

Each kitchen synchronization takes an immutable snapshot of the order items and compares it to the last synchronized snapshot.

Deltas are emitted by production unit:

- Add: new quantity only
- Reduce: removed quantity only
- Modify: notes, course, or allergy changes with unchanged quantity
- Moving a line to another production unit: Reduce on the old unit and Add on the new unit

The order is row-locked during the operation. Revision numbers, request keys, snapshot hashes, and source row references make retries deterministic.

## Stock rule

Only Add KOT items are eligible for ERPNext recipe Material Issue posting. Reduce and Modify KOTs are marked Not Required. Cancellation never creates an automatic Stock Entry reversal. Any physical wastage, return-to-stock, or correction remains an explicit ERPNext stock operation.

## Discounts and UOM

Restaurant quantities use the ERPNext Item stock UOM and UOM `must_be_whole_number` rule. Weighed or fractional products are normalized to three decimal places.

Discount percentage and authorization are operational inputs on Hotel Restaurant Bill Split. The actual financial discount is applied through ERPNext POS Invoice or Sales Invoice `additional_discount_percentage`, and the resulting ERPNext `discount_amount` is copied back for traceability.

## Tables and printing

A Table Cluster groups multiple Hotel Restaurant Tables under one operational order. It does not merge ERPNext invoices. Each settlement split remains an independent ERPNext invoice.

Printer Routes use ERPNext Network Printer Settings and optional Print Formats. Each route produces an idempotent Print Job with bounded retries and Dead Letter status. Multiple routes allow one KOT or bill to be printed on multiple printers without hiding failures inside the transaction that created the order or invoice.

## Production Gate

RC9 adds:

- RESTAURANT_SESSION_CONTROL
- KITCHEN_DELTA_CONTROL
- RESTAURANT_PRINT_CONTROL

A Go decision is blocked by mismatched POS sessions, unsynchronized active orders, cancellation KOT stock posting, duplicate KOT revisions, or failed/dead-letter print jobs.
