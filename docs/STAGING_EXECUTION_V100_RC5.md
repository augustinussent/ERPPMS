# Staging Execution Pack v1.0.0-rc5

RC5 converts the Production Gate from a model into an executable staging workflow. It does not add hotel-operation features and does not create financial or stock transactions.

## Required identity

Before execution, the staging site must expose:

- `HOTEL_PMS_ARTIFACT_SHA256`
- `HOTEL_PMS_IMAGE_DIGEST`
- exact Frappe and ERPNext versions
- a frozen `Hotel Release Manifest`
- an open `Hotel Production Gate Run`

Evidence is accepted only when its release version, normalized source fingerprint, image digest, and package checksum match the installed candidate.

## Execution order

1. Backup database and files.
2. Run migration and build assets.
3. Capture staging preflight.
4. Run the read-only Smoke rehearsal.
5. Capture accounting, stock, and sync-key reconciliation.
6. Build the private cutover bundle.
7. Re-run automated Production Gate checks.
8. Build and verify the filesystem evidence manifest.

## No-double-entry boundary

The RC5 execution module may create only validation evidence, rehearsal records, and private Frappe File records. It never creates or submits:

- Sales Invoice
- POS Invoice
- Payment Entry
- Journal Entry
- Purchase Invoice
- Stock Entry

Accounting and stock results are read from ERPNext documents and ledgers.

## Command

```bash
BENCH_ROOT=/home/frappe/frappe-bench \
SITE=hotel-staging.example.com \
GATE_RUN=HPG-2026-00001 \
EVIDENCE_DIR=/secure/evidence/HPG-2026-00001 \
apps/hotel_pms/ci/run_staging_execution.sh
```

The evidence directory is expected to contain:

- `00-environment.txt`
- `10-migrate.log`
- `20-preflight.json`
- `30-smoke.json`
- `40-reconciliation.json`
- `50-cutover-bundle.json`
- `60-gate-checks.json`
- `evidence-manifest.json`
- `evidence-manifest.sha256`

## Promotion rule

A passed RC5 run is not itself permission to deploy. Parallel-run reconciliation, manual checks, eight department sign-offs, final Go decision, and controlled promotion remain mandatory.
