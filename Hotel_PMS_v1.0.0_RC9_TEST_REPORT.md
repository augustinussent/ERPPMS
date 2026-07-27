# Hotel PMS ERPNext v1.0.0-rc9 Test Report

## Candidate

```text
Version: 1.0.0-rc9
Source fingerprint: 915b5ae2a1839f5416210791c7dd5192084df2be8aaa390931439c6eb2151b83
```

## Static and pure validation

```text
Python files parsed/compiled: 477
JavaScript files checked:     69
JSON files parsed:            174
DocTypes:                     134
Top-level DocTypes:            95
Child DocTypes:                39
Desk pages:                    20
Query reports:                 12
Property-scoped DocTypes:      86
Pure tests passed:            125
```

Contract results:

```text
Base property/scope contract: 0 errors
RC2 financial contract:       0 errors
RC3 stock-path contract:      0 errors
RC4 validation contract:      0 errors
RC5 staging contract:         0 errors
RC6 intelligence contract:    0 errors
RC7 control contract:         0 errors
RC8 distribution contract:    0 errors
RC9 restaurant contract:      0 errors
OpenAPI drift:                0 errors
```

## Bugs caught during validation

1. KOT delta quantity was overwritten by the total row quantity during dictionary composition. Fixed and covered by regression tests.
2. Moving an item between production units initially generated only a modification at the new unit. It now creates a cancellation at the old unit and an addition at the new unit.
3. Discount was briefly applied after the POS payment amount was calculated. It now runs before ERPNext calculates the payment rows.
4. An order with no kitchen snapshot could have passed the original pre-bill comparison. Active quantity now requires an actual synchronized snapshot.
5. Historical RC3 contract assumed KOT stock queueing lived directly in services.py. The contract now follows the RC9 incremental-KOT adapter while retaining fnb_inventory.py as the only Stock Entry creator.

## Full pytest result in this build environment

Full collection stops on four bench-only modules because Frappe is not installed:

- test_intelligence_rc6_integration.py
- test_intelligence_rc7_integration.py
- test_platform_integration.py
- test_restaurant_controls_rc9_integration.py

This is an environment limitation, not a passing bench result. The RC9 bench smoke script is included but was not executed here.

## Still required on a real Frappe/ERPNext v16 bench

- Fresh install and RC8-to-RC9 migration.
- POS Opening and Closing lifecycle.
- Concurrent cashier and KOT operations.
- ERPNext tax, discount, payment, GL, AR, and Stock Ledger reconciliation.
- Network Printer Settings and Print Format integration.
- Multi-property permissions.
- Backup, restore, rollback, and Production Gate evidence.
