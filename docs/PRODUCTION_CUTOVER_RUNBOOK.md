# Production cutover runbook

## T-14 to T-7 days
- Freeze schema changes except production blockers.
- Complete staging migration and restore drill.
- Reconcile accounting, stock, room inventory, deposits, and city ledger.
- Complete security and load tests.

## T-48 hours
- Confirm backups and off-server copy.
- Export configuration and user/property access list.
- Confirm DNS, TLS, email, payment gateway, scheduler, workers, websocket, and monitoring.
- Approve rollback trigger and responsible decision maker.

## Cutover
1. Announce transaction freeze.
2. Take database and file backup; copy off server; record SHA-256.
3. Deploy pinned image and run migrate.
4. Run `restore_smoke_check`, health snapshot, and core transaction smoke tests.
5. Reconcile opening balances and room inventory.
6. Open controlled access to department leads.
7. Obtain final Go decision in Hotel Production Gate Run.

## Rollback triggers
- Migration failure without approved repair.
- Material accounting/stock difference above threshold.
- Property data exposure.
- Duplicate financial transactions.
- Booking inventory race or inability to check in/out.
- Payment callback or POS failure affecting operation.

Rollback means restoring the approved pre-cutover backup on the prior pinned image, then reconciling all transactions entered after freeze.
