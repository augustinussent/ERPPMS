# Roadmap after Hotel PMS v1.0.0-rc7

## Immediate

Execute the Production Gate on isolated Frappe/ERPNext v16 staging and rehearsal benches:

1. Blank install.
2. RC6/RC5 data-copy upgrade to RC7.
3. RC7 bench smoke and source identity verification.
4. Night Audit finding UAT.
5. Payment correction cap, approval, concurrency, and idempotency UAT.
6. Enabled integration health, property isolation, and credential rotation.
7. GL, A/R, tax, cashier, POS, and Stock Ledger reconciliation.
8. Security, performance, restore, and rollback drills.
9. Parallel run and eight departmental sign-offs.
10. Promote the same normalized fingerprint to v1.0.0.

Do not add another feature candidate before these gates are completed. A further RC is justified only by a reproducible defect in executable source.

## After v1.0.0

Proposed v1.1.0 remains advisory intelligence only: cancellation risk, housekeeping workload suggestions, A/R collection priority, group pickup forecast, and read-only revenue briefing.
