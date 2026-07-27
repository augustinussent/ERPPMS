# Hotel PMS ERPNext v1.0.0-rc3

## F&B Operational Depth

Rilis kandidat ini memperdalam Restaurant POS tanpa membuat inventory ledger kedua. Seluruh kuantitas dan nilai stok resmi tetap berasal dari **ERPNext Stock Entry** dan **Stock Ledger Entry**.

## Prinsip satu jalur stok

Setiap `Hotel Outlet` memilih tepat satu kebijakan:

1. **ERPNext POS Finished Goods**  
   `POS Invoice` atau `Sales Invoice` memakai `update_stock = 1`. Recipe Material Issue tidak dijalankan.
2. **Recipe Material Issue**  
   Invoice restoran memakai `update_stock = 0`. Setiap KOT membuat satu `Stock Entry` bertipe `Material Issue` berdasarkan resep.
3. **No Stock Posting**  
   Invoice memakai `update_stock = 0` dan KOT tidak membuat Stock Entry.

Sistem menolak konfigurasi Recipe Material Issue apabila global recipe posting belum diaktifkan atau warehouse sumber belum tersedia.

## Idempotency dan pembatalan

Satu KOT menggunakan base key:

```text
KOT-STOCK:<Hotel Kitchen Ticket>
```

Pembuatan Stock Entry memakai `create_document_once()` dan `Hotel ERP Sync Log`. Jika Stock Entry lama dibatalkan, retry menggunakan revision key seperti `:R2`. Dokumen aktif tidak dapat berjumlah lebih dari satu untuk operasi yang sama.

Pembatalan Stock Entry memakai mekanisme cancel ERPNext. PMS tidak membuat jurnal atau stock reversal buatan. KOT dan Restaurant Order berubah menjadi `Pending` sampai Stock Entry baru diposting atau hasilnya direkonsiliasi.

## Waktu konsumsi

Konsumsi resep dimulai saat order dikirim ke dapur dan KOT dibuat. Invoice dan pembayaran bukan pemicu stok.

Void atau cancellation setelah KOT sudah di-fire tidak mengembalikan bahan secara otomatis. Bahan yang sudah dimasak merupakan wastage. Koreksi fisik harus menggunakan Stock Reconciliation atau Stock Entry ERPNext yang disetujui dengan alasan.

## KDS v2

Status ticket:

```text
New → Accepted → Cooking → Partially Ready → Ready → Served
                    ↘ Recalled
```

Fitur:

- Accept dan Start ticket.
- Progress per item.
- Course grouping.
- Allergy highlighting.
- Guest, room/table, captain, priority, dan target-ready context.
- Ticket aging dan indikator LATE.
- Recall dengan alasan.
- Realtime event `hotel_kds_update`.
- Sound notification opsional di browser.
- Link langsung ke ERPNext Stock Entry.

Recall tidak membalik konsumsi bahan.

## Recipe master

Recipe berada pada `Hotel Outlet Menu Item` sebagai child table `Hotel Menu Recipe Item`.

Setiap baris harus menunjuk:

- ERPNext stock Item.
- Kuantitas dalam Stock UOM item.
- Optional warehouse override.

Outlet warehouse digunakan jika baris recipe tidak memiliki override.

## Menu import

Halaman:

```text
/app/hotel-menu-import
```

CSV mendukung:

```text
item_code,menu_name,rate,kitchen_station,course,allergy_alert,preparation_minutes,recipe_json
```

`recipe_json` berupa array JSON. Preview membuat `Hotel Menu Import Batch` dan mengklasifikasikan row sebagai Insert, Update, Skip, atau Reject. Preview tidak membuat Item, Stock Entry, invoice, atau transaksi keuangan.

## Rekonsiliasi

Report:

```text
/app/query-report/Hotel Restaurant Stock Reconciliation
```

Production Gate memahami tiga kebijakan stok:

- Finished Goods memeriksa Stock Ledger Entry dari POS/Sales Invoice.
- Recipe Material Issue memeriksa Stock Entry per KOT dan Stock Ledger Entry-nya.
- No Stock Posting memastikan invoice tidak melakukan update_stock.

## Gerbang sebelum aktivasi recipe posting

1. Semua ingredient telah menjadi ERPNext stock Item.
2. Stock UOM recipe telah diverifikasi.
3. Warehouse outlet berada di Company yang benar.
4. Opening stock sudah direkonsiliasi.
5. Recipe sample dibandingkan dengan pemakaian aktual.
6. Stock Entry draft dan submit diuji.
7. Negative-stock policy ERPNext diputuskan Finance dan F&B.
8. POS/Sales Invoice terbukti `update_stock = 0` pada recipe mode.
9. KOT retry terbukti tidak membuat Stock Entry ganda.
10. Cancel dan repost menghasilkan revision key, bukan dokumen aktif ganda.
