# Hotel PMS v0.6.0 Validation Report

Validation date: 21 July 2026

## Release scope

Revenue calendar, deterministic quoting, seasons, derived rates, restrictions, rate approvals, vouchers, travel-agent commission, tax/service-charge profile, folio split/transfer/reversal, unified checkout, Payment Request, city ledger/direct bill, cashier shift, and finance reconciliation hooks.

## Static validation completed

| Check | Result |
|---|---:|
| Python files compiled | 197 passed |
| JavaScript files checked with Node | 28 passed |
| JSON files parsed | 77 passed |
| DocTypes audited | 64 passed |
| Duplicate DocType fields | 0 |
| Field-order mismatches | 0 |
| Missing non-child permissions | 0 |
| Invalid child-table references | 0 |
| JavaScript calls to missing Hotel PMS Python methods | 0 of 39 |
| Release metadata checks | Passed |

## Pure-rule tests

18 tests passed across:

- Revenue rules.
- Derived rates and adjustments.
- Voucher discounts.
- Inclusive/exclusive service-charge and tax algebra.
- Stay restriction validation.
- Exact folio split conservation.
- Quote hashing.
- Front-desk room-night and cancellation calculations.
- Housekeeping priority, timing, inspection, SLA, and SOP thresholds.

## Duplicate-entry controls reviewed

- Rate approvals use deterministic idempotency keys.
- Voucher redemption is unique per reservation and retry-safe.
- Travel-agent settlement and Purchase Invoice creation use sync keys.
- Folio transfer and reversal use immutable audit documents and unique request keys.
- Payment Request creation uses a unique Hotel PMS sync key and ERPNext's native request validation.
- City-ledger invoice creation uses per-charge deterministic keys.
- Cashier movements use request-level idempotency keys.
- Submitted Sales Invoice, Payment Entry, and POS Invoice events reconcile PMS links and totals.

## Accounting architecture review

The PMS does not create a second general ledger. The following remain authoritative in ERPNext:

- Sales Invoice and accounts receivable.
- Purchase Invoice and accounts payable.
- Payment Entry and cash/bank movement.
- POS Invoice and posted sales/payment data.
- Payment Request and gateway status.
- Sales Taxes and Charges Template and GL tax posting.
- Customer, Supplier, Item, Cost Center, Account, and Mode of Payment.

Hotel folios, city-ledger folios, rate quotes, cashier shifts, and commission settlements are operational control documents linked to those ERPNext records.

## Not executed in this environment

The following require a real Frappe/ERPNext v16 staging site:

1. `bench migrate` and patch execution.
2. Custom-field creation against the exact ERPNext v16 schema.
3. Page rendering in Desk and mobile browsers.
4. Role and User Permission enforcement.
5. MariaDB concurrent booking, transfer, voucher, and cashier operations.
6. Sales Invoice, Purchase Invoice, Payment Entry, POS Invoice, and Payment Request submit/cancel lifecycle.
7. Payment gateway URL creation, callback, duplicate callback, refund, and failure recovery.
8. ERPNext tax-template calculations against the selected Indonesian configuration.
9. Advance allocation and invoice outstanding reconciliation.
10. Cashier POS child-table/account reconciliation on the deployed ERPNext build.
11. Scheduler and worker execution.
12. Backup, restore, and upgrade rehearsal.
13. End-to-end accounting reconciliation and signed UAT.

## Production recommendation

Do not deploy v0.6.0 directly to production. Install it on a staging site, configure accountant-reviewed tax templates and payment accounts, run every UAT scenario in `docs/REVENUE_BILLING_V060.md`, and verify zero unexplained difference between PMS operational totals and ERPNext accounting reports.
