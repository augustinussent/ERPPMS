# Roadmap after Hotel PMS v1.0.0-rc6

## Immediate: execute the Production Gate

Do not add another feature RC unless staging identifies a defect that changes executable source.

Required work:

1. Blank install on Frappe/ERPNext v16.
2. Upgrade rehearsal from RC5 data copy.
3. RC6 bench smoke and financial-count guard.
4. Night Audit finding UAT with real hotel data.
5. Payment correction concurrency and approval test.
6. GL, A/R, tax, cashier, POS, and Stock Ledger reconciliation.
7. Integration property-isolation and credential-rotation tests.
8. Backup, restore, rollback, security, and performance rehearsals.
9. Parallel run and eight departmental sign-offs.
10. Promote the exact approved fingerprint to v1.0.0.

## After v1.0.0 final: proposed v1.1.0

- Cancellation Risk report calibrated from property history.
- Housekeeping workload optimizer in Suggest mode.
- A/R collection priority recommendations.
- Group pickup forecast.
- Read-only Revenue Manager briefing.
- Optional local explanation model with numeric grounding.

No intelligence module may create financial or stock documents directly. Execution must continue through existing ERPNext-native domain actions and idempotency controls.

## Later: v1.2.0 distribution adapters

- Python Channel Adapter protocol.
- Generic inbound reservation envelope.
- Property-scoped room/rate mapping.
- Idempotent OTA modification and cancellation handling.
- ARI push queue, retry, and dead-letter console.
- First live channel adapter only after certification and Production Gate evidence.
