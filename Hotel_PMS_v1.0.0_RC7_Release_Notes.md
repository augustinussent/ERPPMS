# Hotel PMS ERPNext v1.0.0-rc7 Release Notes

RC7 is a control hotfix. It supersedes RC6 for staging validation.

## Fixed

- Capped automatic deposit refunds at the lower of the selected source Payment Entry amount and the remaining refundable deposit.
- Preserved Ready/Live integration status after a successful health test.
- Made failed enabled integrations remain visible as Production Gate blockers.
- Required successful Test Connection evidence before Ready or Live status.
- Included Purchase Invoice sync-key validation in ERPNext-native integration health.
- Made Draft, Pending Approval, Approved, and Failed payment-correction requests block Go.
- Rejected blank and non-numeric parallel-run values before reconciliation.
- Expanded bench smoke to compare financial-document, GL Entry, and Stock Ledger Entry counts and to verify finding-upsert idempotency.

## Unchanged

- ERPNext remains the only accounting, payment, tax, receivable, and stock ledger.
- Intelligence remains advisory.
- Refund results remain draft ERPNext Payment Entries requiring Finance review.
- No channel-manager adapter or autonomous financial executor was added.
