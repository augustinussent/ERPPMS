# Parallel Run v1.0.0-rc4

Jalankan sistem lama dan Hotel PMS pada periode yang sama menggunakan transaksi operasional yang disepakati. Jangan membuat transaksi keuangan kedua hanya untuk memenuhi parallel run. Bandingkan output dan ledger dari sistem masing-masing.

## Kolom CSV

- `metric_code`
- `department`
- `business_date`
- `reference`
- `legacy_value`
- `pms_value`
- `tolerance`
- `notes`

`variance = abs(legacy_value - pms_value)`.

- Passed: variance tidak melebihi tolerance.
- Warning: variance masih dalam 150% tolerance.
- Failed: variance lebih tinggi.

Warning tetap menghalangi promosi. Ubah tolerance hanya dengan alasan terdokumentasi, bukan agar tabel berubah hijau karena semua orang ingin pulang.

## Minimum period

Gunakan sedikitnya:

- satu hari kerja normal;
- satu hari occupancy tinggi;
- satu night audit;
- satu checkout dengan deposit/refund;
- satu city-ledger atau corporate billing jika digunakan;
- satu restoran/KOT/stock cycle jika F&B digunakan.

## Bukti

Simpan CSV asli, hasil validator JSON, laporan ERPNext, dan laporan sistem lama. Hash CSV disimpan pada Hotel Parallel Run Batch.
