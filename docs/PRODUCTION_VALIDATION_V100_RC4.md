# Hotel PMS v1.0.0-rc4 Production Validation

## Tujuan

RC4 menambahkan mekanisme bukti untuk menjalankan Production Gate pada environment Frappe/ERPNext v16 nyata. Modul ini tidak membuat dokumen uang atau stok. Seluruh pemeriksaan finance dan inventory hanya membaca serta merekonsiliasi dokumen ERPNext.

## Identitas rilis

`Hotel Release Manifest` membekukan:

- versi kandidat dan target promosi;
- normalized source fingerprint;
- SHA-256 paket kandidat;
- pinned Frappe dan ERPNext version;
- candidate container image digest;
- git commit dan package URL.

Source fingerprint menormalisasi satu assignment `hotel_pms.__version__`. Karena itu perubahan label `1.0.0rc4` menjadi `1.0.0` tidak mengubah fingerprint, sedangkan perubahan executable source lain akan mengubahnya.

Konfigurasi site kandidat:

```bash
bench --site <site> set-config hotel_pms_artifact_sha256 <RC4_ZIP_SHA256>
bench --site <site> set-config hotel_pms_image_digest sha256:<RC4_IMAGE_DIGEST>
```

Manifest hanya dapat dibekukan jika installed source, package checksum, Frappe version, ERPNext version, dan image digest sama dengan manifest.

## Immutable rehearsal records

`Hotel Rehearsal Run` menyimpan hasil:

- Blank Install;
- Upgrade;
- Restore;
- Rollback;
- Concurrency;
- Performance;
- Security.

Record menyimpan source fingerprint, image digest, command hash, evidence hash, waktu, duration, result summary, dan RTO jika relevan. Record tidak dapat diedit atau dihapus melalui operasi normal.

Contoh perekaman dari CI:

```bash
export BENCH_PATH=/home/frappe/frappe-bench
export CONTROL_SITE=validation.example.com
export RUN_TYPE="Concurrency"
export ENVIRONMENT_NAME=Staging
export STATUS=Passed
export STARTED_AT=2026-08-01T01:00:00Z
export COMPLETED_AT=2026-08-01T01:04:00Z
export EVIDENCE_PATH=/evidence/concurrency.json
export RESULT_SUMMARY="Last-room test: exactly one reservation succeeded."
ci/record_rehearsal.sh
```

## Parallel run

Unggah CSV melalui `/app/hotel-production-gate` atau validasi dahulu:

```bash
python ci/run_parallel_reconciliation.py \
  examples/parallel_run_reconciliation_rc4.csv \
  --output parallel-result.json
```

Metric dasar wajib:

- `RESERVATIONS`
- `ROOM_NIGHTS`
- `ROOM_REVENUE`
- `TAX_TOTAL`
- `PAYMENTS`
- `DEPOSITS`
- `REFUNDS`
- `AR_OUTSTANDING`
- `CASHIER_CASH`

Jika properti sudah memiliki Restaurant Order, `FNB_REVENUE` dan `STOCK_MOVEMENT` juga wajib.

Batch dengan Warning atau Failed tetap menjadi blocker. Nilai tidak diposting ke ERPNext. Data hanya berfungsi sebagai evidence reconciliation.

## Production Gate execution

1. Bangun RC4 package dan container.
2. Konfigurasikan candidate package checksum dan image digest pada site.
3. Buat lalu freeze Release Manifest.
4. Buat Gate Run dengan manifest tersebut.
5. Jalankan blank install dan upgrade rehearsal.
6. Jalankan concurrency, performance, dan security test.
7. Jalankan isolated restore dan rollback rehearsal.
8. Import parallel-run CSV.
9. Jalankan Automated Checks.
10. Lampirkan evidence manual.
11. Minta sign-off delapan departemen.
12. Beri keputusan Go atau No-Go.

Setelah final decision, check dan sign-off pada gate tersebut tidak dapat diubah. Koreksi memerlukan Gate Run baru. Setelah Go, satu keputusan Rollback masih dapat dicatat; manifest kemudian menjadi Revoked.

## Promotion tanpa perubahan executable source

Pada clean copy dari commit yang sama:

```bash
python ci/promote_release.py \
  --expected-fingerprint <FROZEN_SOURCE_FINGERPRINT> \
  --target-version 1.0.0 \
  --apply
```

Bangun ZIP dan container final, lalu hitung:

```bash
sha256sum hotel_pms_erpnext_v1.0.0.zip
# catat juga image digest hasil build final
```

Pada Gate Run yang telah Go, gunakan `Prepare Promotion` dan masukkan final package SHA-256 serta final image digest. Manifest berubah menjadi `Promotion Prepared` dan menyimpan identitas kandidat serta final secara terpisah.

Setelah deploy final:

```bash
bench --site <site> set-config hotel_pms_artifact_sha256 <FINAL_ZIP_SHA256>
bench --site <site> set-config hotel_pms_image_digest sha256:<FINAL_IMAGE_DIGEST>
bench --site <site> execute hotel_pms.production_validation.verify_installed_release \
  --kwargs '{"manifest_name":"HRM-..."}'
```

Verification harus mengembalikan `passed: true`.

## Larangan double entry

Production Validation tidak boleh membuat:

- Sales Invoice;
- POS Invoice;
- Payment Entry;
- Journal Entry;
- Purchase Invoice;
- Stock Entry.

CI RC4 memeriksa larangan tersebut. Accounting dan stock gate membaca ERPNext sebagai sumber resmi.
