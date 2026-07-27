# Hotel PMS ERPNext v1.1.0
## Adopsi Localization, WhatsApp, dan Guest Document

## 1. Tujuan rilis

Rilis ini mengadopsi pola bernilai tinggi dari perkembangan terbaru Kamra PMS tanpa mengambil ledger keuangan atau stok mereka. Seluruh posting akuntansi tetap dilakukan oleh dokumen ERPNext.

Batas yang tidak boleh dilanggar:

```text
Hotel localization / WhatsApp / guest documents
≠ Sales Invoice
≠ POS Invoice
≠ Payment Entry
≠ Journal Entry
≠ Purchase Invoice
≠ Stock Entry
```

PMS hanya menyimpan konfigurasi, status operasional, referensi dokumen, dan audit log. ERPNext tetap menjadi sumber resmi GL, piutang, pembayaran, pajak, dan stok.

## 2. Country-pack Indonesia

`Hotel Property` mengambil country, default currency, dan tax ID dari ERPNext `Company`. Country-pack Indonesia menyediakan konteks tampilan:

- Currency: IDR.
- Locale: `id-ID`.
- Label pajak: PBJT.
- Label nomor pajak: NPWP.

Country-pack tidak menentukan tarif pajak secara otomatis. Tarif, basis, akun, dan template wajib disiapkan melalui `Hotel Tax Profile` dan ERPNext `Sales Taxes and Charges Template`, lalu ditinjau Finance.

### Kontrak pajak

Ketika pajak atau service charge tidak nol:

1. `Hotel Tax Profile` harus memiliki ERPNext `Sales Taxes and Charges Template`.
2. Template harus berasal dari Company yang sama dengan properti.
3. Account service charge, pajak, dan rounding harus berasal dari Company yang sama.
4. Profile harus berstatus telah ditinjau Finance.
5. Quote boleh menampilkan breakdown PMS, tetapi invoice hanya memposting tax rows dari ERPNext template.

### Pencegahan pajak ganda

- Folio individual dan city ledger menolak campuran beberapa tax profile dalam satu invoice.
- Group folio dipisah berdasarkan `billing customer + tax profile`.
- Satu Sales Invoice hanya menerima satu ERPNext tax template.
- Modul localization tidak pernah menambahkan baris pada child table `taxes`.

## 3. WhatsApp Meta Cloud API

### Master

Buat `Hotel Channel Connection` per properti dan isi:

- Meta phone number ID.
- Graph API version yang dipin, misalnya `vXX.X` sesuai environment yang diuji.
- Permanent access token.
- Webhook verify token.
- Meta app secret.
- Bahasa template.
- Nama template booking confirmation, self check-in, dan payment request.

Token dan secret menggunakan field `Password` Frappe.

### Endpoint webhook

```text
/api/method/hotel_pms.communications.meta_webhook
```

GET digunakan untuk verifikasi Meta. POST memverifikasi `X-Hub-Signature-256` dengan app secret sebelum memproses status atau pesan masuk.

### Outbound queue

Booking confirmation, self-check-in link, payment request, dan pesan staf melewati `Hotel Guest Message` serta background queue.

```text
Business transaction committed
→ message row dibuat dengan idempotency key
→ enqueue after commit
→ Meta API send
→ status callback
→ Sent / Delivered / Read / Failed / Dead Letter
```

Gangguan Meta tidak membatalkan reservation, invoice, atau Payment Request. Retry menggunakan message row yang sama. Secure variables seperti guest link disimpan terenkripsi untuk retry dan dibersihkan setelah sukses.

### Inbound

Pesan masuk dicocokkan dengan Contact, Customer, dan reservasi aktif. Staf dapat mengubah pesan menjadi `Hotel Maintenance Ticket` melalui action terkontrol dengan idempotency key. Pembuatan tiket tidak membuat transaksi finansial.

## 4. Private guest documents

Dokumen ID dan address proof hanya tersedia ketika global photo toggle aktif.

Pipeline:

1. Tolak payload terlalu besar sebelum decode.
2. Decode base64.
3. Validasi JPEG, PNG, atau WebP.
4. Tolak image bomb atau jumlah pixel berlebihan.
5. Terapkan orientasi EXIF.
6. Resize sesuai batas konfigurasi.
7. Re-encode menjadi JPEG untuk membuang metadata dan payload tersembunyi.
8. Simpan sebagai private Frappe `File`.
9. Satu file aktif per slot; upload baru mengganti dan menghapus file lama.

Guest hanya dapat upload sebelum check-in pada status `Tentative` atau `Confirmed`. Mode `Verify and Discard` menghapus dokumen saat checkout dan melalui daily cleanup.

## 5. Implementasi

```bash
cd ~/frappe-bench
bench --site erp.domainhotel.com backup --with-files
```

Ganti source aplikasi, kemudian:

```bash
bench --site erp.domainhotel.com migrate
bench build --app hotel_pms
bench --site erp.domainhotel.com clear-cache
bench restart
```

Konfigurasi awal:

1. Periksa ERPNext Company: Country, Default Currency, Tax ID.
2. Buat atau tinjau ERPNext Sales Taxes and Charges Template.
3. Hubungkan template ke Hotel Tax Profile.
4. Tandai `Accountant Reviewed` setelah pengujian Finance.
5. Biarkan WhatsApp OFF selama konfigurasi.
6. Buat Hotel Channel Connection.
7. Verifikasi webhook dan template pada Meta test number.
8. Uji booking saat Meta aktif dan saat Meta sengaja tidak tersedia.
9. Uji photo toggle ON/OFF serta Verify-and-Discard.

## 6. UAT minimum

- Quote dan Sales Invoice menghasilkan total yang sama.
- Tidak ada tax row manual atau invoice kedua dari localization.
- Retry invoice mengembalikan dokumen ERPNext yang sama.
- Group charge dengan tax profile berbeda menghasilkan invoice terpisah.
- Booking sukses ketika Meta API gagal.
- Retry WhatsApp tidak membuat message row kedua.
- Duplicate delivery callback aman.
- Signature webhook salah ditolak.
- User Property A tidak melihat message Property B.
- Guest upload sesudah check-in ditolak.
- Private file tidak dapat diakses tanpa izin.
- Verify-and-Discard benar-benar menghapus record File dan file fisik setelah checkout.

## 7. Batas pengujian

Source ini telah melalui pemeriksaan statis dan pure-rule tests, tetapi belum dijalankan pada bench ERPNext/Frappe v16 nyata dalam environment build. Migration, MariaDB concurrency, Meta callback, private-file backup/restore, permission matrix, tax calculation, dan GL reconciliation tetap wajib dilakukan pada staging.
