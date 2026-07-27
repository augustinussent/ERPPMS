# Roadmap after Hotel PMS v1.0.0-rc9

## Immediate staging gate

1. Install RC9 on an isolated Frappe/ERPNext v16 bench.
2. Run `ci/run_rc9_bench_smoke.sh`.
3. Rehearse RC8-to-RC9 migration using a production data copy.
4. Validate ERPNext POS Opening and Closing for each outlet and cashier role.
5. Validate KOT revision concurrency and recipe stock posting.
6. Reconcile discount, tax, POS payments, GL, AR, and Stock Ledger.
7. Test Network Printer Settings, multiple routes, retries, and dead-letter recovery.
8. Complete Production Gate and departmental sign-offs.

## Next implementation candidates

### P0: Restaurant staging corrections

Only create RC10 when staging identifies an executable defect. Configuration, printer mapping, menu mapping, and data cleanup do not require a new candidate.

### P1: Kitchen course orchestration

- Course hold and fire controls.
- Expo view across Production Units.
- Ready-by-course coordination.
- No automatic stock reversal.

### P1: Controlled table and captain transfer

- Transfer audit record.
- Active KOT context update.
- Table availability locking.
- Property and outlet isolation.

### P1: Restaurant settlement orchestration

- Combined-payment allocation helper across independent ERPNext invoices.
- No financial invoice merge.
- Exact rounding residual assignment.
- Refund and correction matrix reuse.

### P2: Procurement and food-cost intelligence

- Recipe theoretical cost from ERPNext Item Valuation Rate or BOM.
- Variance report against submitted Stock Entries.
- Purchase planning recommendations.
- No custom COGS or inventory ledger.

### P2: Offline-tolerant captain interface

- Local draft queue with explicit synchronization state.
- Idempotent server request keys.
- Conflict resolution, not silent last-write-wins.
- Financial submission remains online-only.
