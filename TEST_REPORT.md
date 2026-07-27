# Hotel PMS ERPNext v0.7.0 — Test Report

Tanggal pemeriksaan: 21 Juli 2026

## Hasil

```text
Python files parsed/compiled         222
JavaScript files checked              32
JSON files validated                  86
DocTypes structurally audited         72
Pure-rule tests passed                21
Potential undefined globals            0
Duplicate DocType fields               0
Field-order errors                     0
Missing Hotel child DocTypes           0
Missing JavaScript API contracts        0
Missing Hotel PMS Settings fields       0
Security invariant errors              0
ZIP integrity errors                    0
```

## Pemeriksaan yang dijalankan

### Python

- `compileall` untuk seluruh source.
- Symbol-table scan untuk potensi global variable yang tidak didefinisikan.
- Import/function syntax.
- Controller and scheduler path presence.

### JavaScript

- `node --check` untuk seluruh file JavaScript.
- Pencocokan method string UI terhadap fungsi Python yang tersedia.
- Public-page output escaping.
- Token fragment/session handling.

### JSON dan DocType

- Semua JSON dapat diparse.
- Tidak ada duplicate fieldname.
- Semua field terdapat pada field_order.
- Semua Hotel child-table references tersedia.
- Settings references dari Python tersedia pada Hotel PMS Settings.

### Pure-rule tests

Total 21 test seluruh project, termasuk:

- room-night dan stay calculations;
- cancellation fee calculations;
- housekeeping priority, timing, inspection, SLA, dan SOP threshold;
- revenue rate, voucher, tax, and split conservation rules;
- email/phone normalization;
- token expiry/usage rules;
- blacklist channel behavior;
- anonymization eligibility.

### Security invariants

Pemeriksaan memastikan:

- tidak ada public booking deposit yang diambil dari guest payload;
- tidak ada dokumentasi/code token baru dalam query string;
- raw token tidak disimpan sebagai token database;
- public token endpoints menggunakan reservation/customer scope;
- guest cancellation tidak dapat memproses no-show atau fee waiver;
- guest action logs bersifat append-only melalui normal permissions;
- public property/room images harus berupa `/files/` attachments;
- public text di-escape sebelum masuk DOM;
- availability publik memakai group room block dan Reservation validation.

### ZIP

- 375 file.
- `ZipFile.testzip()` tidak menemukan file rusak.
- SHA-256 dicatat terpisah.

## Belum diuji pada bench nyata

Pengujian berikut wajib dilakukan pada staging ERPNext/Frappe v16:

1. `bench migrate` dan patch v0.7.0.
2. Website route melalui Nginx/reverse proxy.
3. MariaDB simultaneous last-room booking.
4. Group room block concurrency.
5. Email queue dan fragment links.
6. Payment Gateway Account dan callback.
7. Payment Request submit/cancel/retry.
8. Customer/Contact creation dan duplicate resolution.
9. Frappe Customer merge pada data nyata.
10. Customer rename pada naming rule site saat anonymization.
11. Print/PDF rendering.
12. Permissions untuk Front Desk, Hotel Manager, Accounts Manager, dan Guest.
13. Token expiry scheduler dan blacklist expiry.
14. Backup dan restore.
15. End-to-end accounting reconciliation.
16. Browser Android, iOS, desktop, dan accessibility checks.
17. Load, rate-limit, reverse-proxy, dan penetration testing.

## Kesimpulan

Rilis lolos pemeriksaan source statis dan pure-rule tests. Statusnya adalah **siap untuk deployment staging dan UAT**, bukan langsung production. Klaim produksi sebelum concurrency, payment callback, permission, merge, anonymization, dan restore test selesai akan lebih bersifat optimisme daripada quality assurance.
