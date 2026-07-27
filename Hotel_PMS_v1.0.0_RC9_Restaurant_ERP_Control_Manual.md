# Hotel PMS ERPNext v1.0.0-rc9
## Restaurant ERP Control Manual

## Release status

`v1.0.0-rc9` is a staging release candidate. It supersedes RC8 because executable restaurant, cashier-session, kitchen-delta, printing, and Production Gate code changed.

## What was adopted from URY

URY's strongest design is its deliberate use of standard ERPNext transaction objects around a restaurant workflow. RC9 adapts the following patterns:

1. POS Opening and Closing as hard cashier-session controls.
2. Incremental KOT rather than resending the entire order.
3. Production-unit routing for kitchen work.
4. Float quantities governed by ERPNext UOM rules.
5. Transaction-level discount controls written into ERPNext invoice fields.
6. Table grouping without prematurely releasing tables when billing is incomplete.
7. Multiple printer routes with observable failures.
8. Operational delay and failure alerts.

RC9 does not import URY's application code or replace the Hotel PMS domain model.

## ERPNext synchronization model

| Hotel PMS record | ERPNext authority | Synchronization rule |
|---|---|---|
| Hotel Cashier Shift | POS Opening Entry / POS Closing Entry | Shift links to one submitted matching opening and closing document |
| Hotel Restaurant Order | No financial authority | Operational order only |
| Hotel Restaurant Bill Split | POS Invoice / Sales Invoice | One split creates at most one idempotent ERPNext invoice |
| Direct restaurant payment | POS Invoice payment rows / Payment Entry | ERPNext remains the monetary record |
| Restaurant tax | Sales Taxes and Charges Template | No custom tax ledger |
| Kitchen Addition KOT | Stock Entry Material Issue when recipe mode is enabled | Only positive Add deltas can consume ingredients |
| Kitchen Reduction KOT | Explicit ERPNext stock correction when required | Never auto-reversed |
| Print Job | Network Printer Settings | Operational queue only |
| Table Cluster | None | Seating context only, never a bill ledger |

## Initial setup

### 1. Migrate

```bash
bench --site <staging-site> migrate
```

RC9 creates six DocTypes and custom links on ERPNext POS Opening Entry and POS Closing Entry.

### 2. Review outlets

For each Hotel Outlet:

- Set the ERPNext POS Profile.
- Keep `Require POS Opening Entry` enabled for controlled restaurant operations.
- Set Cashier Discount Limit.
- Review warehouse, cost center, income account, tax profile, and inventory posting policy.

### 3. Review production units

Migration creates a Hotel Kitchen Production Unit from each existing menu `kitchen_station`, then links the menu row to it.

Review:

- Unit name.
- Warning minutes.
- Outlet and property.
- Enabled status.

### 4. Configure printer routes

Create Hotel Restaurant Printer Route records for each printer destination.

- Purpose KOT may use a Hotel Kitchen Ticket Print Format.
- Purpose Bill may use a POS Invoice or Sales Invoice Print Format.
- Purpose Both uses the document's default format.
- Multiple enabled routes produce separate idempotent jobs.

Printing is optional. A configured route that repeatedly fails becomes a Production Gate blocker.

## Daily cashier flow

1. Create an ERPNext POS Opening Entry for the cashier and POS Profile.
2. Open a Hotel Cashier Shift for the same outlet.
3. Use `Link POS Opening Entry` on the shift.
4. Confirm that ERPNext Session Status is Open.
5. Run restaurant operations.
6. Create and submit ERPNext POS Closing Entry.
7. Link it to the Hotel Cashier Shift.
8. Close the Hotel Cashier Shift after cash reconciliation.

A shift cannot close as Closed when the required ERPNext closing entry is missing or mismatched. It remains in Closing Review.

## Kitchen revision flow

First fire:

```text
Order snapshot
→ KOT revision 1
→ Add deltas by Production Unit
→ optional ERPNext recipe Stock Entry
```

Subsequent edits:

```text
Current order
− previous snapshot
→ Add / Reduce / Modify KOT revisions
```

Examples:

- Quantity 1 becomes 3: Addition KOT quantity 2.
- Quantity 3 becomes 1: Cancellation KOT quantity 2.
- Note changes from “normal” to “no salt”: Modification KOT quantity unchanged.
- Item moves from Cold Kitchen to Hot Kitchen: Cancellation at Cold Kitchen and Addition at Hot Kitchen.

A reduction is not a Stock Entry reversal. This is intentional because food may already be prepared or wasted.

## Discounts

The outlet defines the cashier discount threshold.

- Discount at or below the threshold requires a reason.
- Discount above the threshold requires an authorized Hotel Manager, Accounts Manager, or System Manager.
- ERPNext calculates the actual tax, rounding, grand total, payments, and discount amount.
- Hotel PMS records the resulting ERPNext discount amount for traceability only.

## Fractional quantities

RC9 reads ERPNext Item stock UOM:

- UOM with `Must be Whole Number`: `1.5` is rejected.
- Fractional UOM: quantities are normalized to three decimals.

This applies to restaurant order rows and bill-split rows.

## Restaurant Control console

Open:

```text
/app/hotel-restaurant-control
```

The console shows:

- Outlet POS controls.
- Open and Closing Review cashier shifts.
- Kitchen revisions and stock status.
- Operational alerts.
- Queued, failed, and dead-letter print jobs.

## Table clusters

Use Merge Tables from Hotel Restaurant Order. All selected tables must:

- Belong to the same outlet.
- Be unique.
- Not belong to another active order.
- Not be Cleaning or Out of Service.

The cluster is released when the order is billed or cancelled. This does not merge financial documents. Bill splits remain separate ERPNext invoices.

## Production Gate

RC9 adds three mandatory automated controls:

### RESTAURANT_SESSION_CONTROL

Fails when:

- Controlled outlet has no POS Profile.
- Open shift lacks a matching submitted Open POS Opening Entry.
- Closed shift lacks a matching submitted Closed POS Closing Entry.

### KITCHEN_DELTA_CONTROL

Fails when:

- Active order differs from its kitchen snapshot.
- Active order was never sent to the kitchen.
- Cancellation KOT has a Stock Entry or stock status other than Not Required.
- Duplicate KOT revision exists.

### RESTAURANT_PRINT_CONTROL

Fails when:

- Print Job is Failed or Dead Letter.
- Enabled Printer Route lacks a valid printer or copy count.

## Upgrade handling

Existing menu rows with a kitchen station are mapped automatically to new Production Units.

Existing active orders are not backfilled with fabricated kitchen snapshots. They must be reviewed and synchronized by an operator before billing. This prevents a migration from falsely claiming that a live order was already fired to the kitchen.

## Required staging tests

Before promotion:

1. RC8-to-RC9 migration on a database copy.
2. POS Opening/Closing linkage for multiple cashiers.
3. Concurrent KOT synchronization.
4. Add, Reduce, Modify, and Production Unit move scenarios.
5. Recipe Stock Entry for additions only.
6. Wastage/correction procedure after cancellation.
7. Tax and discount reconciliation on POS Invoice and Sales Invoice.
8. Cashier payment and closing reconciliation.
9. Multi-printer success, retry, and dead-letter behavior.
10. Table-cluster billing and release.
11. Multi-property permission isolation.
12. Production Gate and rollback rehearsal.
