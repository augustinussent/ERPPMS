# Manual Hotel PMS ERPNext v1.0.0-rc5

## Tujuan

RC5 menyediakan alat untuk menjalankan kandidat rilis pada staging dan mengumpulkan bukti yang dapat diverifikasi. Tidak ada fitur transaksi hotel baru.

## Prasyarat

- Bench Frappe/ERPNext v16 aktif.
- Site staging terisolasi dari production.
- Backup database dan file berhasil.
- Release Manifest RC5 sudah `Frozen`.
- Production Gate Run sudah dibuat.
- `HOTEL_PMS_ARTIFACT_SHA256` sesuai ZIP kandidat.
- `HOTEL_PMS_IMAGE_DIGEST` sesuai container kandidat.
- Worker, scheduler, Redis, MariaDB, dan websocket aktif.

## Langkah eksekusi

```bash
cd ~/frappe-bench

export BENCH_ROOT="$PWD"
export SITE="hotel-staging.example.com"
export GATE_RUN="HPG-2026-00001"
export EVIDENCE_DIR="$PWD/sites/$SITE/private/hotel-pms-evidence/$GATE_RUN"

apps/hotel_pms/ci/run_staging_execution.sh
```

Script melakukan backup, migrate, build, clear-cache, preflight, Smoke rehearsal, rekonsiliasi, cutover bundle, dan verifikasi checksum.

## Pemeriksaan preflight

- Aplikasi `frappe`, `erpnext`, dan `hotel_pms` terpasang.
- Manifest cocok dengan source, ZIP, image, dan versi terpasang.
- MariaDB dapat diakses dan isolation level terbaca.
- DocType inti tersedia.
- Custom field integrasi ERPNext tersedia.
- Scheduler aktif.
- Worker heartbeat kurang dari 15 menit.
- Encryption key tersedia.
- Developer mode mati di luar development.
- Storage site writable dan ruang kosong minimal 2 GB.
- Seluruh user hotel memiliki property assignment.

## Smoke rehearsal

Smoke rehearsal hanya membaca Settings, Property, Reservation, Folio, ERP Sync Log, metadata ERPNext, dan import modul API. Ia tidak membuat reservasi, invoice, pembayaran, atau stok.

## Rekonsiliasi

Snapshot memakai fungsi rekonsiliasi Production Gate yang sama untuk membaca:

- Folio dan Sales Invoice.
- Deposit/refund dan Payment Entry.
- Cashier variance.
- Restaurant invoice dan Stock Ledger.
- KOT recipe dan Stock Entry.
- Duplicate active `custom_hotel_sync_key`.

Bila terdapat dua dokumen aktif dengan sync key sama, snapshot gagal.

## Cutover bundle

Bundle disimpan sebagai private Frappe File dan memuat:

- Identitas artefak.
- Gate checks.
- Rehearsal.
- Parallel run.
- Sign-off.
- Preflight.
- Daftar evidence dan checksum.

Secret, password, token, API key, dan encryption key selalu disensor.

## Kriteria lulus

- `STAGING_PREFLIGHT`: Passed.
- `SMOKE_REHEARSAL`: Passed.
- `RECON_SNAPSHOT`: Passed.
- `CUTOVER_BUNDLE`: Passed.
- Seluruh check Production Gate lain sesuai RC4 tetap Passed.
- Tidak ada warning atau failed pada parallel run.
- Delapan departemen memberikan sign-off.

## Batas

RC5 belum menggantikan penetration test, peak-load test, restore drill, rollback drill, dan parallel run manusia. Script hanya membuat bukti lebih sulit dipalsukan, bukan membuat manusia otomatis teliti. Sayangnya teknologi belum sejauh itu.

## Fingerprint kandidat

```text
098c93c8992d71ccbcbcbc11bc3472028cf30db14b825b5edb5978e75d09a5eb
```

Bukti yang dibuat oleh source dengan fingerprint lain tidak boleh dipakai untuk promosi kandidat ini.
