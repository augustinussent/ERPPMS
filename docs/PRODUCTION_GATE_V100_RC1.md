# Hotel PMS v1.0.0-rc1 Production Gate

This release does not claim production approval. It adds the controls and evidence model needed to decide whether a specific environment may go live.

## Gate categories
1. Platform and migration
2. Accounting reconciliation
3. Inventory and operations
4. Security
5. Reliability and disaster recovery
6. Performance
7. Operational readiness

## Required evidence
- Exact Frappe, ERPNext, and Hotel PMS image/tag/digest
- Blank installation and upgrade rehearsal logs
- Accounting and stock reconciliation output
- Last-room/table/capacity concurrency result
- Security and property-isolation test report
- Backup checksum and isolated restore report with measured RPO/RTO
- Load-test result and slow-query review
- Parallel-run variance report
- Department sign-offs
- Approved cutover and rollback plan

A Go decision is blocked while any mandatory check is not Passed/Not Applicable or any department sign-off is pending/rejected.
