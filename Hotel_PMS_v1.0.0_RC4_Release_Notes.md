# Hotel PMS ERPNext v1.0.0-rc4 Release Notes

## Added

- Frozen Release Manifest dengan candidate/final artifact identities.
- Normalized source fingerprint untuk promosi RC ke final tanpa perubahan executable code.
- Immutable rehearsal records untuk blank install, upgrade, restore, rollback, concurrency, performance dan security.
- Parallel-run CSV reconciliation dengan tolerance dan mandatory metrics.
- Immutable validation evidence untuk manual checks, final decision dan promotion preparation/finalization.
- Production Gate checks untuk manifest, rehearsal dan parallel run.
- Promotion guard serta rollback revocation.
- `ci/record_rehearsal.sh`.
- `ci/run_parallel_reconciliation.py`.
- `ci/promote_release.py`.
- Evidence-producing blank install, upgrade, restore dan rollback scripts.

## Changed

- Gate Run wajib dibuat dari Frozen Release Manifest.
- Gate results dan sign-off terkunci setelah final decision.
- Warning pada parallel run menjadi blocker.
- Candidate artifact checksum dan image digest harus dikonfigurasi pada site.

## Accounting safety

Production Validation tidak membuat Sales Invoice, POS Invoice, Payment Entry, Journal Entry, Purchase Invoice atau Stock Entry. ERPNext tetap satu-satunya accounting dan stock ledger.

## Release status

RC4 belum menjadi production release. Promotion ke `1.0.0` memerlukan evidence dari target environment dan department sign-off.
