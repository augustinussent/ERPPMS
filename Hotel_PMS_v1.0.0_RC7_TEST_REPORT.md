# Hotel PMS ERPNext v1.0.0-rc7 Test Report

## Release status

RC7 is a staging candidate and supersedes RC6. It is a control hotfix produced after static staging review found release-blocking defects in payment-correction bounds, integration readiness, and parallel-run input validation.

## Static and pure-rule validation

| Check | Result |
|---|---:|
| Python files parsed | 428 |
| JavaScript files checked | 64 |
| JSON files parsed | 159 |
| DocTypes audited | 122 |
| Desk pages | 17 |
| Query reports | 12 |
| Property-scoped DocTypes | 76 |
| Pure-rule tests | 65 passed |
| RC2 financial contract errors | 0 |
| RC3 stock-path contract errors | 0 |
| RC4 production-validation errors | 0 |
| RC5 staging-execution errors | 0 |
| RC6 intelligence-control errors | 0 |
| RC7 hotfix contract errors | 0 |
| API documentation drift | 0 |
| Python/JSON/JavaScript/shell syntax errors | 0 |

## RC7 regression coverage

The pure tests and source contracts validate:

- automatic refund amount is capped at the lower of the source Payment Entry amount and the remaining refundable deposit;
- Ready or Live integration status requires an enabled connection, Shipped/Adapter maturity, a successful test timestamp, and passed mandatory checks;
- a successful retest preserves Ready/Live, while a failed enabled connection remains a Production Gate blocker;
- Draft, Pending Approval, Approved, and Failed payment-correction records block Go;
- Purchase Invoice is included in ERPNext sync-key health checks;
- blank or nonnumeric parallel-run values are rejected rather than interpreted as zero;
- a complete 11-metric parallel-run sample passes with zero unexplained variance.

## Package-independent limits

No live Frappe/ERPNext v16 bench was available in the build environment. The following remain mandatory on isolated staging and rehearsal benches:

- RC6/RC5 database-copy upgrade to RC7;
- MariaDB concurrency and permission tests;
- real Payment Entry refund, cancellation, and General Ledger reconciliation;
- Night Audit repeated-run idempotency against operational data;
- integration credential rotation, callback, retry, and property isolation;
- accounting, tax, cashier, POS, and Stock Ledger reconciliation;
- security, performance, restore, and rollback drills;
- parallel run and eight departmental sign-offs.

RC7 must not be promoted until those gates produce matching immutable evidence for the final packaged checksum, source fingerprint, and container digest.
