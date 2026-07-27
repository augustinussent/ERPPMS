# Hotel PMS ERPNext v1.0.0-rc1 — Production Gate Manual

## Status
This package is a release candidate. It adds production-approval controls, but this build environment did not contain a live Frappe/ERPNext v16 bench. Therefore no real migration, accounting, stock, security, load, or restore result is claimed.

## Installation rehearsal
Use a disposable staging site. Pin exact Frappe and ERPNext versions and the container digest. Build the custom image from `deploy/Dockerfile`, set `HOTEL_PMS_IMAGE_DIGEST`, install the app, run migrate, tests, scheduler, workers, websocket, email, payment, and backup checks.

For upgrade rehearsal, run `ci/run_upgrade_rehearsal.sh` against a database restored from v0.9.0. Do not substitute a blank install for an upgrade test.

## Production Gate page
Open `/app/hotel-production-gate`.

1. Create a gate run for the exact property/environment.
2. Enter exact expected Frappe version, ERPNext version, and image digest.
3. Run automated checks.
4. Attach evidence for every manual check.
5. Obtain sign-off from Front Office, Housekeeping, Engineering, Sales & Banquet, F&B, Finance, IT, and Management.
6. Only System Manager can record the final Go, No-Go, or Rollback decision.

A Go decision is blocked while a mandatory check is pending, warning/failed where mandatory, or a department sign-off is not approved.

## Automated checks
- Installed app/version/image match.
- Database connectivity and scheduler heartbeat.
- Backup freshness and checksum verification.
- ERP sync queue and webhook dead-letter queue.
- Property-access assignment.
- Folio/invoice, deposit/refund, travel-agent, city-ledger, and cashier reconciliation.
- Restaurant invoice and Stock Ledger linkage.
- Public booking and webhook prerequisites.

## Manual evidence
- Accountant review.
- End-to-end operations UAT.
- Penetration test and dependency/container scan.
- Secret rotation.
- Isolated restore, disaster-recovery, and rollback drills.
- Load test and slow-query/index review.
- Parallel run, training, SOP/escalation, support roster, cutover and rollback plan.

## Test tools
- `ci/run_concurrency_gate.py`
- `ci/run_performance_gate.py`
- `ci/run_security_gate.sh`
- `ci/run_restore_drill.sh`
- `ci/run_upgrade_rehearsal.sh`

## Go-live rule
The software becomes a production release only after a specific environment passes the gate with traceable evidence. Passing static checks on source code is not a substitute.
