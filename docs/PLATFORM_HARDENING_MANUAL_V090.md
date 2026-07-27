# Manual Hotel PMS ERPNext v0.9.0 — Platform Hardening

## 1. Tujuan rilis

v0.9.0 memperkuat fondasi sebelum production gate. Rilis ini tidak berfokus pada fitur jualan baru, melainkan isolasi properti, setup yang aman, migrasi data, integrasi API, webhook, monitoring, backup, pengujian, dan kontrol keamanan.

## 2. Multi-property access control

### 2.1 Master akses

Buka **Hotel User Property Access** dan buat satu baris untuk setiap kombinasi pengguna dan properti.

Field penting:

- User
- Property
- Enabled
- Default Property
- Access Level: Operational, Manager, atau Read Only
- Can View Consolidated
- Reviewed By dan Reviewed At

`Administrator` dan `System Manager` tetap dapat mengakses semua properti. Pengguna operasional tanpa assignment tidak dapat membaca atau mengubah DocType PMS yang memiliki property scope.

### 2.2 Property switcher

Property switcher muncul pada navbar Desk untuk pengguna yang memiliki assignment. Pilihan disimpan sebagai user default `hotel_pms_current_property`.

Switcher adalah default konteks UI. Pembatasan keamanan tetap dilakukan server-side oleh permission query dan document permission hook.

### 2.3 Shared guest master

ERPNext Customer dan Hotel Guest Profile tetap shared. Catatan operasional per properti disimpan pada **Hotel Guest Property Note**, sehingga preferensi atau risiko khusus properti tidak dicampur menjadi catatan global.

### 2.4 ERPNext permissions

Property scope PMS tidak menggantikan permission ERPNext. Untuk transaksi core ERPNext, batasi Company, Cost Center, Warehouse, POS Profile, dan Account melalui User Permission dan Role Permission Manager.

## 3. Onboarding wizard

Halaman:

```text
/app/hotel-onboarding
```

Hanya System Manager yang dapat menjalankan onboarding.

Urutan:

1. Buat session dengan Company, Property Name, dan Abbreviation.
2. Jalankan **Scan**.
3. Periksa Company, Cost Center, Warehouse, Property, dan Settings.
4. Jalankan **Build Plan**.
5. Tinjau action Create, Reuse, atau Upsert.
6. Jalankan **Apply Safely**.
7. Export configuration untuk staging/production.

Wizard memakai natural key dan idempotency key. Menjalankan ulang session yang sama akan menggunakan master yang sudah ada dan tidak membuat Cost Center, Warehouse, atau Hotel Property ganda.

Contoh configuration tersedia pada `examples/onboarding_configuration.json`.

## 4. Migration importer

Halaman:

```text
/app/hotel-migration-importer
```

### 4.1 Source preset

- eZee
- Cloudbeds
- Generic PMS
- Spreadsheet

### 4.2 Entity

- Customer
- Room Type
- Room
- Reservation
- Rate Calendar
- Deposit Review

Deposit Review tidak pernah membuat Payment Entry otomatis. Setiap baris hanya ditandai **Review**, karena migrasi saldo tanpa rekonsiliasi adalah cara mahal untuk memindahkan masalah lama ke sistem baru.

### 4.3 Proses

1. Buat Hotel Migration Batch.
2. Pilih property dan source preset.
3. Upload CSV UTF-8.
4. Isi mapping JSON bila header tidak cocok dengan preset.
5. Jalankan Dry Run.
6. Periksa semua baris Insert, Update, Skip, Reject, atau Review.
7. Perbaiki source/mapping.
8. Dry Run ulang.
9. Commit Import.
10. Rekonsiliasi hasil dengan sumber.

Rollback otomatis hanya berlaku untuk dokumen draft/non-accounting yang dibuat batch dan belum memiliki transaksi turunan.

## 5. Versioned API v1

Prefix:

```text
/api/method/hotel_pms.api.v1.<endpoint>
```

Dokumentasi:

- `docs/openapi-v1.json`
- `docs/hotel-pms-v1.postman_collection.json`

Endpoint awal:

- properties
- availability
- reservation
- create_reservation
- room_status
- health

Gunakan token authentication Frappe dan role **Hotel API User**. Semua request dibatasi ke property assignment pengguna.

Write endpoint wajib memakai:

```text
X-Idempotency-Key: <unique-request-key>
```

Key yang sama dengan payload berbeda ditolak. Retry payload yang sama mengembalikan hasil sebelumnya atau melanjutkan operasi aman bila attempt lama gagal.

## 6. Outbound webhooks

### 6.1 Subscription

Buat **Hotel Webhook Subscription**:

- Property, atau kosong untuk global subscription milik System Manager
- HTTPS Endpoint URL
- HMAC Secret
- Event Patterns
- Timeout
- Maximum Attempts

Contoh pattern:

```text
reservation.*
payment.submitted
housekeeping.updated
```

Private, loopback, link-local, multicast, dan reserved network address ditolak untuk mengurangi risiko SSRF.

### 6.2 Signature

Header delivery:

```text
X-Hotel-Event
X-Hotel-Timestamp
X-Hotel-Signature: sha256=<digest>
X-Idempotency-Key
```

Signature dibuat dari:

```text
HMAC-SHA256(secret, timestamp + "." + raw_body)
```

Receiver wajib memeriksa signature, batas umur timestamp, dan idempotency key.

### 6.3 Retry

Status delivery:

```text
Pending → Processing → Sent
                     ↘ Retry → Dead Letter
```

Retry memakai exponential backoff. Dead Letter tidak dikirim ulang diam-diam; replay dilakukan eksplisit oleh manager.

## 7. Platform console dan observability

Halaman:

```text
/app/hotel-platform-console
```

Menampilkan:

- Property metrics
- Room dan occupancy
- Month revenue berdasarkan submitted Sales Invoice yang terhubung ke reservation
- Open service issues
- Disk usage
- Backup freshness
- Failed sync
- Dead-letter webhook
- Migration errors
- Users tanpa property assignment
- Assignment yang belum direview
- Guest privacy retention yang perlu ditinjau

Scheduler membuat worker heartbeat lima menit sekali dan health snapshot setiap jam. Endpoint API health dapat dipakai oleh external uptime monitor. Websocket tetap membutuhkan probe eksternal.

## 8. Backup verification

Tombol **Verify Latest Backup**:

- Memilih file database backup terbaru
- Membaca file penuh
- Menghitung SHA-256
- Mencatat ukuran dan waktu backup
- Membuat Hotel Backup Verification

Ini bukan restore test. Production gate tetap membutuhkan restore ke site isolasi, pemeriksaan login, migrasi, dokumen, file, GL, dan waktu pemulihan.

## 9. Privacy retention review

Scheduler menandai Guest Profile sebagai **Pending Anonymization** bila:

- retention date telah lewat;
- tidak ada active stay;
- tidak ada submitted Sales Invoice outstanding;
- profile belum retention hold.

Data tidak dihapus otomatis. Proses anonymization tetap melewati identity verification dan approval.

## 10. CI dan test runner

Static CI menjalankan:

- Python parse
- JSON parse
- DocType field contract
- Property-scope coverage
- OpenAPI/Postman drift check
- Pure business-rule tests

Bench integration menggunakan runner berlabel:

```text
self-hosted, frappe-v16
```

Aktifkan repository variable:

```text
RUN_FRAPPE_INTEGRATION=true
```

Runner harus memiliki `BENCH_PATH` dan `SITE`. Script `ci/run_bench_tests.sh` memasang/migrasikan app, menjalankan Frappe tests, dan membuat health snapshot.

## 11. Security deployment

Ikuti `docs/SECURITY_RUNBOOK_V090.md`:

- TLS dan HSTS
- CSP
- Referrer-Policy
- X-Content-Type-Options
- request body limit
- rate limit
- secret rotation
- dependency/container scan
- property access review
- isolated restore drill

## 12. Upgrade dari v0.8.0

```bash
cd ~/frappe-bench
bench --site erp.domainhotel.com backup
```

Ganti source app, lalu:

```bash
bench --site erp.domainhotel.com migrate
bench build --app hotel_pms
bench --site erp.domainhotel.com clear-cache
bench restart
```

Sesudah migrasi:

1. Buat Hotel User Property Access untuk seluruh user operasional.
2. Uji user satu properti, multi-properti, read-only, dan tanpa assignment.
3. Review permission ERPNext Company/Cost Center/Warehouse.
4. Jalankan onboarding hanya di staging.
5. Uji importer dengan salinan CSV kecil.
6. Biarkan outbound webhook OFF sampai endpoint receiver siap.
7. Konfigurasi health recipients.
8. Jalankan backup verification.
9. Jalankan restore drill pada site isolasi.
10. Aktifkan runner CI Frappe v16.
