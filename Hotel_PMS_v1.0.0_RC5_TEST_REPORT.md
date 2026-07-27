# Hotel PMS ERPNext v1.0.0-rc5 Test Report

## Scope

Static and pure-rule validation of the RC5 Staging Execution Pack. No active Frappe/ERPNext v16 bench was available in this build environment.

## Source identity

```text
Version                1.0.0rc5
Normalized fingerprint 098c93c8992d71ccbcbcbc11bc3472028cf30db14b825b5edb5978e75d09a5eb
```

The fingerprint covers executable Python, JSON, JavaScript, HTML, CSS, shell scripts, workflows, deployment configuration, hooks, and patches. Only the release-label assignment in `hotel_pms/__init__.py` is normalized for controlled promotion.

## Successful checks

```text
Python files parsed/compiled        398
JavaScript files checked             57
JSON files parsed                    149
DocTypes audited                     114
Desk pages                            16
Query reports                         11
Property-scoped DocTypes              70
Shell scripts checked                  7
Pure-rule tests passed                51
RC2 financial guard errors             0
RC3 stock-path errors                  0
RC4 validation contract errors         0
RC5 execution contract errors          0
DocType/property contract errors       0
OpenAPI/Postman drift errors            0
```

## RC5 rules tested

- Recursive removal of token, password, API secret, encryption key, and similar values from evidence.
- Stable evidence SHA-256 generation.
- Required preflight checks cannot disappear silently.
- Evidence must match release version, normalized source fingerprint, image digest, and artifact checksum.
- Multiple active ERPNext documents with one Hotel PMS sync key are detected.
- Cancelled ERPNext documents do not create false duplicate-key failures.
- Filesystem evidence manifests detect missing files, changed sizes, and changed checksums.

## Double-entry contract

`hotel_pms/staging_execution.py` was checked to ensure it does not create:

```text
Sales Invoice
POS Invoice
Payment Entry
Journal Entry
Purchase Invoice
Stock Entry
```

The module creates only validation evidence, rehearsal records, and a private Frappe File containing the cutover bundle. Accounting and stock reconciliation read ERPNext documents and ledgers.

## Evidence-tool self-test

A temporary staging evidence directory containing all seven required execution outputs was built, hashed, and verified successfully using:

```text
ci/build_evidence_manifest.py
ci/verify_staging_bundle.py
```

## Not executed here

- Frappe/ERPNext database migration.
- MariaDB transaction and concurrency behavior.
- Redis worker and scheduler execution.
- Real `bench backup --with-files`.
- ERPNext tax, GL, AR, POS, Payment Entry, and Stock Ledger reconciliation.
- Meta WhatsApp callback.
- Private File access through the web server.
- Restore and rollback drill.
- Peak-load and penetration test.
- Parallel run and department sign-off.

These remain mandatory Production Gate checks on a pinned staging environment.
