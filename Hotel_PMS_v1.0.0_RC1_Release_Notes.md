# Hotel PMS ERPNext v1.0.0-rc1 Release Notes

## Added
- Controlled Production Gate Run with automated checks, manual evidence, departmental sign-offs, and final decision.
- Exact Frappe/ERPNext version and container-digest pin verification.
- Accounting checks for folio invoices, deposits/refunds, travel-agent invoices, city-ledger exposure, and cashier variance.
- Restaurant POS and Stock Ledger linkage checks.
- Backup RPO and restore RTO fields.
- Upgrade rehearsal, restore drill, concurrency, performance, and security scripts.
- Pinned custom-image Dockerfile and cutover/rollback runbooks.

## Important
This is not a claim of production readiness. It has not been run against a live Frappe/ERPNext v16 bench in this build environment. General availability v1.0.0 requires a passed Production Gate on the target environment.
