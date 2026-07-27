# Hotel PMS ERPNext v1.0.0-rc7 Hotfix Manual

## Purpose

RC7 fixes release-blocking defects identified while preparing RC6 staging validation. It contains no new business feature.

## Upgrade

```bash
cd ~/frappe-bench
bench --site hotel-staging.example.com backup --with-files
# replace apps/hotel_pms with the frozen RC7 source
bench --site hotel-staging.example.com migrate
bench build --app hotel_pms
bench --site hotel-staging.example.com clear-cache
bench restart
```

## Required UAT

1. Confirm the installed ZIP checksum, normalized source fingerprint, Frappe version, ERPNext version, and image digest.
2. Re-run the Night Audit intelligence smoke twice and confirm no duplicate finding fingerprints or financial/stock count changes.
3. Test Payment Correction on a disposable data copy:
   - source Payment Entry amount below total refundable deposit;
   - refund maximum equals the source amount, not the total deposit;
   - one draft refund is created after approval;
   - retry creates no second draft;
   - GL Entry and Stock Ledger Entry counts remain unchanged.
4. Test every enabled integration:
   - a passing test preserves Ready/Live;
   - a failing test becomes Failed and blocks Production Gate;
   - Live cannot be saved without enabled status, successful test, and mandatory checks.
5. Validate a parallel-run CSV containing blanks and confirm it is rejected.
6. Complete the remaining Production Gate rehearsals, reconciliation, parallel run, and departmental sign-offs.

## Promotion rule

Promote only the exact normalized RC7 source fingerprint. Any executable source change requires a new candidate and fresh evidence.
