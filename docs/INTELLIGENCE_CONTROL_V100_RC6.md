# Hotel PMS v1.0.0-rc6 Intelligence & Control

## Purpose

RC6 adds governed operational intelligence without creating a second accounting, payment, tax, receivable, or stock ledger. ERPNext remains authoritative for all financial and inventory postings.

## Operational pages

- `/app/hotel-intelligence-console`
- `/app/query-report/Hotel Night Audit Findings`
- `Hotel Payment Correction`
- `Hotel Integration Connection`

## Governed decision lifecycle

Every intelligence run records:

1. property and business date;
2. trigger type;
3. source version and input hash;
4. input signals;
5. deterministic recommendation;
6. confidence;
7. approval or rejection;
8. execution result and outcome.

The initial RC6 agents are advisory. `Manual` and `Suggest` modes are supported operationally. `Autopilot` requires a separate approval flag and RC6 contains no automatic finance or stock execution path.

## Night Audit anomaly scan

The scanner checks:

- checked-in reservations without a folio;
- stale in-house stays past departure;
- checked-out stays with an open folio;
- positive folio charges without Hotel Tax Profile;
- invoiced or closed folios without a submitted ERPNext Sales Invoice;
- failed ERP synchronization records;
- duplicate completed ERP sync keys;
- cashier variance beyond the configured threshold;
- unresolved restaurant recipe stock posting.

A rerun is idempotent by finding fingerprint. A finding absent from the latest run for the same property and business date is automatically resolved. False positives stay closed until explicitly reopened.

## Payment correction matrix

RC6 never edits the General Ledger directly. The legal operational action is derived from the current ERPNext Payment Entry state:

- Draft Payment Entry: `Delete Draft` after approval.
- Submitted hotel deposit with refundable balance: `Create Refund` using the existing idempotent hotel refund function. The result is a new **draft** ERPNext Payment Entry and is never submitted automatically.
- Cancelled, unknown, non-hotel, or otherwise unsafe state: `Manual Review`.

A correction request records reason, original state, allowed actions, maximum refundable amount, approver, idempotency key, and resulting ERPNext document.

## Integration maturity registry

Maturity statuses are explicit:

- `Shipped`: complete in-product path exists.
- `Adapter`: contract/provider path exists but external credentials or certification are still required.
- `Recipe`: supported through documented API, webhook, CSV, or operational procedure.
- `Planned`: not available.

Initial registry entries:

- ERPNext Native Accounting: Shipped.
- Meta WhatsApp Cloud API: Shipped.
- Hotel PMS Outbound Webhooks: Shipped.
- Hotel PMS API v1: Shipped.
- Generic CSV Migration: Shipped.
- Generic Channel Manager Adapter: Planned.

No provider can be marked Live unless its definition is Shipped or Adapter and all mandatory go-live checks are Passed.

## Grounded explanation guard

An optional explanation may be attached to a deterministic decision. Free-form text is not used as decision input. Numeric statements in the explanation must be supported by numbers in the stored recommendation. Unsupported financial or percentage claims are rejected.

The explanation cannot execute a decision or replace the deterministic recommendation.

## Production Gate additions

RC6 adds these mandatory checks:

- `INTELLIGENCE_GOVERNANCE`
- `PAYMENT_CORRECTION_CONTROL`
- `INTEGRATION_READINESS`

A Go decision is blocked by unsafe autopilot configuration, unresolved Critical findings, failed or approved-but-unexecuted payment corrections, or a Live integration with invalid maturity or incomplete mandatory checks.

## Real-bench smoke

`ci/run_rc6_bench_smoke.sh` runs on a prepared Frappe/ERPNext v16 bench. It:

- installs or migrates the app;
- runs RC6 integration tests;
- seeds the integration registry;
- runs the Night Audit scan;
- verifies that the scan and registry seed did not change counts of Sales Invoice, POS Invoice, Payment Entry, Journal Entry, Purchase Invoice, or Stock Entry;
- optionally attaches smoke evidence to an existing Production Gate Run.

## Explicit non-goals

RC6 does not add:

- an AI-generated rate or tax calculation;
- automatic rate, reservation, refund, invoice, or stock execution;
- a second payment ledger;
- a second A/R ledger;
- a second stock ledger;
- a live OTA/channel-manager adapter;
- an LLM provider or remote guest-data transfer.
