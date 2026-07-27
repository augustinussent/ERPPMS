# Hotel PMS ERPNext v1.0.0-rc8 Test Report

## Candidate identity

```text
Version:            1.0.0-rc8
Source fingerprint: e2b620795f1bdf0f3a883a0f206446d0e9f13d6cd2c9cd9e81b092a776e8022f
Target platform:    Frappe 16 / ERPNext 16
Python declaration: >=3.10
```

## Scope

RC8 adds distribution, iCal inventory blocks, pre-arrival forms, controlled check-in context, occupant document handling, and turnover planning. This report covers static syntax, property scope, financial/stock creation guards, historical RC contracts, pure rules, API documentation drift, and package structure.

## Automated results

```text
Python files parsed/compiled                     453
JavaScript files syntax-checked                    64
JSON files parsed                                167
DocTypes audited                                 128
Property-scoped DocTypes                          81
Desk pages                                        19
Query reports                                     12
RC8 DocTypes                                       6
Pure-rule and source-contract tests               98

Core property-scope errors                         0
RC2 financial-contract errors                      0
RC3 stock-path errors                              0
RC4 validation-contract errors                     0
RC5 staging-contract errors                        0
RC6 intelligence-contract errors                   0
RC7 control-hotfix errors                          0
RC8 distribution-contract errors                   0
OpenAPI/Postman drift                              0
Shell syntax errors                                0
```

## RC8 rule coverage

The pure suite covers:

- Local date handling without UTC day shifts.
- Exclusive iCal DTEND semantics.
- Strict overlap where touching stays are not conflicts.
- UID and exact-range echo deduplication.
- Generic host-block classification.
- Decimal room-rate calculation.
- HTTPS/public-IP URL validation.
- Folded iCal line parsing.
- Deterministic room recommendation.
- Turnover-minute calculation.
- One-time answer snapshot and required-field validation.
- Distribution property-scope contracts.
- Provider maturity governance.
- HMAC signature and no-redirect source contracts.
- iCal token/rate-limit/privacy contracts.
- Foreign-currency Finance-review guard.
- Per-connection iCal sync interval.
- Frappe/ERPNext v16 and Python 3.10 compatibility declarations.
- Prohibition on direct creation of ERPNext financial/stock documents by RC8 modules.

## Financial and stock creation guard

The following modules were scanned:

```text
hotel_pms/distribution.py
hotel_pms/prearrival.py
hotel_pms/turnover.py
```

No direct creation pattern was found for:

```text
Sales Invoice
POS Invoice
Payment Entry
Journal Entry
Purchase Invoice
Stock Entry
```

The RC8 bench smoke also snapshots counts for those documents plus GL Entry and Stock Ledger Entry before and after setup. That smoke requires a real bench and was not executed in this build environment.

## Bench-only tests not executed here

The build environment does not contain the `frappe` Python module or a MariaDB/Redis bench. The following integration suites therefore remain staging obligations rather than local failures:

```text
hotel_pms.tests.test_platform_integration
hotel_pms.tests.test_intelligence_rc6_integration
hotel_pms.tests.test_intelligence_rc7_integration
RC8 migration and distribution smoke on Frappe/ERPNext v16
```

## Required staging evidence

- Blank installation and RC7-to-RC8 upgrade.
- Generic iCal import/export against real OTA feeds.
- DNS rebinding/private-address/redirect regression.
- Generic JSON HMAC, duplicate, concurrency, modification, and cancellation cases.
- Provider room/rate mapping isolation.
- Foreign-currency review path.
- Check-in against clean, dirty, unavailable, and blocked rooms.
- One-time pre-arrival submission under concurrency.
- Occupant file permission, purge, backup, and restore.
- Turnover task idempotency and cleaner conflict review.
- GL, AR, taxes, cashier, POS, and Stock Ledger reconciliation.
- Full Production Gate and departmental sign-off.

## Verdict

The source package is internally consistent and suitable for staging validation. It is not yet production-approved because the real Frappe/ERPNext v16, provider callback, ledger reconciliation, security, restore, rollback, and UAT evidence has not been produced in this environment.
