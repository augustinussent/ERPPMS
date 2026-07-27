# Hotel PMS ERPNext v0.9.0 — Test Report

## Validation completed in build environment

| Check | Result |
|---|---:|
| Python files parsed/compiled | 319 |
| JavaScript files checked with Node | 53 |
| JSON files parsed | 129 |
| DocTypes audited | 100 |
| Desk pages audited | 13 |
| Property-scoped operational DocTypes | 63 |
| API v1 endpoints in generated schema | 6 |
| Pure business-rule tests passed | 29 |
| DocType duplicate-field errors | 0 |
| Field-order contract errors | 0 |
| Property-scope coverage errors | 0 |
| OpenAPI/Postman drift errors | 0 |
| JavaScript syntax errors | 0 |

## Rules tested

- Revenue and cancellation calculations inherited from earlier releases.
- Housekeeping and service rules inherited from earlier releases.
- Webhook event-pattern matching.
- Webhook exponential retry cap.
- Deterministic request hashing.
- HMAC signature determinism.
- Migration natural-key normalization.
- Property-scope declaration coverage.
- API documentation generation consistency.

## Security checks implemented

- Hashed API idempotency record keys.
- Server-side property assignment enforcement.
- Read-only property assignments.
- API role guard.
- Mandatory idempotency key for reservation creation.
- HTTPS-only webhooks.
- Private, loopback, link-local, reserved, and multicast webhook address rejection.
- HMAC signature and delivery idempotency header.
- Guest/privacy operational records receive property references for permission filtering.
- Onboarding restricted to System Manager.
- Accounting deposits remain review-only during migration.

## Not executed in this build environment

The package was not installed into a running Frappe/ERPNext v16 bench here. The following remain mandatory in staging:

- `bench --site <site> migrate` from v0.8.0.
- MariaDB row-level permission and concurrency tests.
- ERPNext Company/Cost Center/Warehouse permission interaction.
- Real worker and scheduler heartbeat.
- Redis/RQ jobs and websocket availability.
- Outbound HTTPS webhook delivery.
- Email health alerts.
- Real backup location and isolated restore drill.
- Accounting, stock, tax, POS, and city-ledger reconciliation.
- Playwright journeys against live Desk and guest pages.
- Reverse-proxy CSP, HSTS, rate-limit, and upload-limit testing.

## CI status

The repository contains:

- Static GitHub Actions job runnable on GitHub-hosted Ubuntu.
- Conditional bench integration job requiring a self-hosted runner labelled `frappe-v16`.
- `ci/run_bench_tests.sh` for migrate, Frappe tests, heartbeat, health snapshot, backup, and checksum verification.
- Playwright scaffold for browser journeys.

A successful static build is not equivalent to production approval. v1.0 requires the real-bench and operational acceptance gates listed in the roadmap.
