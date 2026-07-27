# Hotel PMS ERPNext v1.0.0-rc4 Test Report

## Scope

This report covers source-level validation for the RC4 Production Validation Pack. It does not claim that a real Frappe/ERPNext bench, MariaDB, Redis, workers, browser, accounting ledger, stock ledger, restore drill, or load test was executed in this build environment.

## Automated results

```text
Python files parsed/compiled           390
JavaScript files syntax-checked         57
JSON files parsed                      149
DocTypes audited                       114
Desk pages                              16
Query reports                           11
Property-scoped DocTypes                70
Pure-rule tests passed                  47
Static/DocType contract errors           0
RC2 financial creation guard errors      0
RC3 stock-path contract errors           0
RC4 production-validation errors         0
OpenAPI/Postman drift errors              0
Shell syntax errors                       0
```

Normalized executable-source fingerprint:

```text
0284a885b47f6d165cecf913d4157c88f6a9efa1555bf33c80dee6fb63960bb5
```

The fingerprint normalizes only the `hotel_pms.__version__` assignment. A test verified that changing `1.0.0rc4` to `1.0.0` preserves the fingerprint, while changing another executable source byte changes it.

## RC4 contracts verified

- Release Manifest, Rehearsal Run, Parallel Run Batch/Row and Validation Evidence DocTypes exist.
- Gate Run carries manifest, source fingerprint, candidate artifact checksum and promotion state.
- Candidate and final package/image identities are stored separately.
- New property-bound validation records use server-side property scoping.
- Manifest, rehearsal, parallel-run and evidence records reject normal edits/deletes.
- Final decision is immutable except for a subsequent Rollback after Go.
- Rollback revokes Frozen, Promotion Prepared or Promoted manifests.
- Production Validation source does not create Sales Invoice, POS Invoice, Payment Entry, Journal Entry, Purchase Invoice or Stock Entry.
- Parallel-run CSV validates numeric values, non-negative tolerances and mandatory metrics.
- Warning or Failed parallel batches block release promotion.
- Promotion preparation requires a Go gate, all rehearsals, a Passed parallel run and exact frozen candidate identity.
- Final deployment verification requires promoted version, source fingerprint, package checksum and image digest to match.

## Test suites

The combined pure-rule suite passed 47 tests covering:

- reservation overlap and front-office rules;
- guest portal and privacy rules;
- Housekeeping/Engineering rules;
- rate, voucher and billing rules;
- restaurant/service rules;
- platform and Production Gate rules;
- localization/communication adoption rules;
- recipe and stock-path rules;
- RC4 fingerprint, parallel reconciliation, rehearsal matching and promotion blockers.

## Not executed here

The following remain mandatory on staging or isolated rehearsal environments:

- clean Frappe/ERPNext v16 installation;
- upgrade from a production-like database copy;
- MariaDB concurrency and row-lock behavior;
- Sales Invoice, Payment Entry, AR and General Ledger reconciliation;
- POS Invoice, Stock Entry and Stock Ledger reconciliation;
- Redis queues, scheduler and websocket behavior;
- Meta WhatsApp callback and retry behavior;
- private-file backup and restore;
- security scan plus manual penetration/property-isolation test;
- peak-load and slow-query testing;
- isolated restore and rollback drills;
- parallel run and departmental UAT/sign-off.

Until those records exist and the Production Gate is Approved with a Go decision, RC4 remains a staging candidate.
