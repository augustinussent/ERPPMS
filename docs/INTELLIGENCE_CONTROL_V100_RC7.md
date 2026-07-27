# Hotel PMS v1.0.0-rc7 Control Hotfix

RC7 is a defect-only release candidate derived from RC6. It does not add a ledger, transaction type, integration provider, or business module.

## Fixed payment-correction exposure

The maximum automatic refund is now:

```text
min(source Payment Entry amount, remaining refundable hotel deposit)
```

A correction tied to one Payment Entry can no longer use the full reservation deposit balance when that balance is larger than the selected source payment. The refund still creates one draft ERPNext Payment Entry through the existing governed refund path and remains unsubmitted until Finance reviews it.

## Fixed integration lifecycle

- A successful Test Connection preserves an existing Ready or Live state.
- A failed test marks the enabled connection Failed.
- Ready and Live require the connection to be enabled, a successful test result, and all mandatory go-live checks.
- Production Gate examines every enabled connection, not only those currently labelled Live.
- Purchase Invoice sync-key readiness is included in ERPNext-native integration health.

## Fixed payment gate

Draft, Pending Approval, Approved, and Failed Hotel Payment Correction records all block Go. Only Executed or Cancelled records are considered closed.

## Fixed parallel-run input

The command-line validator rejects missing columns, empty legacy/PMS values, and non-numeric values before variance classification. Empty cells can no longer be interpreted as matching zeros.

## Accounting and stock boundary

RC7 does not create a second accounting or stock ledger. Authoritative records remain ERPNext Sales Invoice, POS Invoice, Payment Entry, Purchase Invoice, Journal Entry, Stock Entry, General Ledger, Accounts Receivable, and Stock Ledger.
