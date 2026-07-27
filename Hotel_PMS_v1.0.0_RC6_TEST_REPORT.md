# Hotel PMS ERPNext v1.0.0-rc6 Test Report

## Result

Static, contract, syntax, packaging-source, and pure-rule validation passed. RC6 was not executed on a live Frappe/ERPNext v16 bench in this build environment.

## Source inventory

```text
Python files                         425
JavaScript files                      64
JSON files                           159
DocTypes                             122
Desk pages                            17
Script/Query reports                  12
Property-scoped DocTypes              76
RC6 DocTypes                           8
```

## Automated results

```text
Pure-rule tests passed                58
Python parse/compile errors             0
JSON parse errors                       0
JavaScript syntax errors                0
Shell syntax errors                     0
DocType field-order errors               0
Property-scope contract errors           0
RC2 financial guard errors               0
RC3 stock-path errors                    0
RC4 validation errors                    0
RC5 staging-execution errors              0
RC6 intelligence-control errors           0
OpenAPI/Postman drift errors              0
```

## RC6-specific contracts verified

- Intelligence module does not directly create Sales Invoice, POS Invoice, Payment Entry, Journal Entry, Purchase Invoice, or Stock Entry.
- Payment refund execution reuses `hotel_pms.front_desk.create_refund_payment_entry`.
- Refund results are drafts and are not submitted automatically.
- Advisory Night Audit decisions declare zero financial-document creation.
- Every property-bearing RC6 DocType has query and document permission hooks and a platform property mapping.
- Integration Definition is global/shared; Integration Connection remains property-scoped.
- Production Gate includes Intelligence Governance, Payment Correction Control, and Integration Readiness.
- RC6 scheduler and migration patch are present.
- Static CI invokes RC6 contracts and pure-rule tests.
- Prepared-bench CI invokes the RC6 smoke script.

## Pure rules covered

- Autopilot requires Autopilot mode, confidence threshold, and explicit approval.
- Numeric payload removes free-form strings and booleans.
- Grounded explanations accept supported Indonesian currency/percentage figures.
- Unsupported financial figures are rejected.
- Draft Payment Entry correction only permits Delete Draft.
- Submitted hotel deposit permits Create Refund within refundable balance.
- Unknown submitted payments remain Manual Review.

## Source fingerprint

```text
275c82bca1e430878cb9f3e834b5310045ac5924305612546ae8e1bf905f3a7c
```

The version assignment is normalized by the fingerprint function so an approved RC can be promoted to `1.0.0` without changing the executable fingerprint. Any other executable-source change invalidates prior evidence.

## Not executed here

The following remain mandatory on an actual staging bench:

- Frappe/ERPNext v16 installation and migration.
- RC5-to-RC6 database upgrade rehearsal.
- New DocType metadata sync and index creation.
- Night Audit scan against hotel operational data.
- Concurrent scan and correction requests under MariaDB row locking.
- Payment Correction approval and idempotent refund draft creation.
- ERPNext Payment Entry submission/cancellation and General Ledger reconciliation.
- Property-isolation tests with multiple users and properties.
- Integration connection credential and callback tests.
- Worker, scheduler, Redis queue, and realtime behavior.
- Backup, restore, rollback, performance, and security rehearsals.
- Parallel run and departmental sign-off.
