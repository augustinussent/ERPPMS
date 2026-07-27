# Manual Implementasi Hotel PMS ERPNext v1.0.0-rc4

## Status rilis

`v1.0.0-rc4` adalah staging candidate. Rilis ini menyediakan alat pelaksanaan Production Gate, tetapi tidak mengklaim bahwa gate hotel Anda sudah lulus.

## Fitur RC4

### Frozen Release Manifest

Manifest mengikat kandidat ke:

- source fingerprint;
- ZIP SHA-256;
- Frappe version;
- ERPNext version;
- container image digest;
- git commit;
- target promosi `1.0.0`.

Manifest Draft dapat dibekukan hanya ketika identitas environment cocok. Setelah Frozen, perubahan dilakukan melalui action terkontrol. Setelah Go dan promosi, manifest menyimpan checksum paket serta image digest final. Rollback akan mengubah manifest menjadi Revoked.

### Rehearsal Evidence

Jenis rehearsal:

1. Blank Install
2. Upgrade
3. Restore
4. Rollback
5. Concurrency
6. Performance
7. Security

Setiap record menyimpan evidence checksum, source fingerprint dan image digest. Hasil dari source atau image berbeda tidak akan memenuhi gate.

### Parallel-run Reconciliation

CSV membandingkan hasil sistem lama dan Hotel PMS. Batch memeriksa tolerance serta metric wajib. Warning dan Failed adalah blocker.

### Immutable Gate Evidence

Manual evidence, final decision dan release promotion menghasilkan `Hotel Validation Evidence`. Evidence tidak dapat diedit. Final decision tidak dapat diganti, kecuali keputusan Go dapat diikuti Rollback.

### Controlled Promotion

Promosi memerlukan:

- semua automated check Passed;
- seluruh manual check Passed/Not Applicable dengan evidence;
- delapan department sign-off Approved;
- Go decision;
- seluruh rehearsal sesuai frozen artifact;
- parallel run Passed;
- checksum final package dan final image digest.

## Upgrade dari RC3

```bash
cd ~/frappe-bench
bench --site erp.domainhotel.com backup --with-files
```

Ganti source dengan RC4, kemudian:

```bash
bench --site erp.domainhotel.com migrate
bench build --app hotel_pms
bench --site erp.domainhotel.com clear-cache
bench restart
```

Konfigurasikan identitas kandidat:

```bash
bench --site erp.domainhotel.com set-config \
  hotel_pms_artifact_sha256 <RC4_ZIP_SHA256>

bench --site erp.domainhotel.com set-config \
  hotel_pms_image_digest sha256:<RC4_IMAGE_DIGEST>
```

## Urutan penggunaan

1. Buka `/app/hotel-production-gate`.
2. Buat Release Manifest.
3. Freeze manifest.
4. Buat Gate Run.
5. Jalankan rehearsal dan upload evidence.
6. Import parallel-run CSV.
7. Jalankan Automated Checks.
8. Lengkapi manual evidence.
9. Jalankan sign-off.
10. Buat final decision.
11. Build source final dari commit sama menggunakan promotion script.
12. Catat final artifact checksum dan image digest melalui Prepare Promotion.
13. Deploy final package.
14. Jalankan `verify_installed_release`; action ini baru mengubah status menjadi `Promoted`.

## ERPNext dan double entry

RC4 tidak menambahkan posting finansial atau stok. Pemeriksaan accounting hanya membaca:

- Sales Invoice dan POS Invoice;
- Payment Entry;
- Purchase Invoice;
- Accounts Receivable;
- Stock Entry dan Stock Ledger Entry;
- folio references dan sync log.

Tidak ada journal, invoice, payment atau stock transaction yang dibuat oleh Production Validation.

## Syarat staging

- Frappe v16 dan ERPNext v16 dipin ke versi exact.
- Database staging berasal dari backup yang sah dan telah dianonimkan bila diperlukan.
- Worker, scheduler dan websocket aktif.
- Candidate ZIP checksum dan image digest tersedia.
- Environment rehearsal terisolasi.
- Finance menyediakan laporan pembanding.
- Setiap departemen menentukan approver.

## Batas pengujian build ini

Source RC4 telah diuji secara statis dan dengan pure-rule tests. Environment build tidak menjalankan MariaDB, Redis, workers, scheduler, browser, Meta callback, Stock Ledger, General Ledger atau restore nyata. Seluruh bukti tersebut harus dibuat pada environment hotel.
