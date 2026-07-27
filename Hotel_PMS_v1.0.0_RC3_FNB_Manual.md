# Manual Implementasi v1.0.0-rc3

## 1. Upgrade

```bash
cd ~/frappe-bench
bench --site erp.domainhotel.com backup --with-files
bench --site erp.domainhotel.com migrate
bench build --app hotel_pms
bench --site erp.domainhotel.com clear-cache
bench restart
```

## 2. Pilih kebijakan stok outlet

Buka `Hotel Outlet`.

### ERPNext POS Finished Goods

Gunakan bila menu dijual sebagai stock Item jadi. Invoice restoran memotong stok melalui `update_stock`.

### Recipe Material Issue

Gunakan bila bahan baku ingin dipotong saat KOT dibuat.

Isi:

- Recipe Source Warehouse.
- Recipe Stock Entry Mode: Draft atau Submit.
- Cost Center.

Aktifkan `Hotel PMS Settings → Enable Recipe Stock Posting` hanya sesudah seluruh setup diuji.

### No Stock Posting

Gunakan untuk outlet yang belum mengelola persediaan melalui PMS. Invoice tidak mengubah stok.

## 3. Siapkan ingredient

Pada ERPNext Item:

- `Maintain Stock` aktif.
- Stock UOM benar.
- Company dan warehouse tersedia.
- Opening stock benar.

## 4. Siapkan recipe

Buka `Hotel Outlet Menu Item`:

1. Aktifkan `Use Recipe Consumption`.
2. Tambahkan ingredient.
3. Masukkan qty dalam Stock UOM ingredient.
4. Gunakan warehouse override hanya bila diperlukan.
5. Simpan.

## 5. KDS v2

Buka:

```text
/app/hotel-kitchen-display
```

Urutan operasi:

1. Captain mengirim order ke kitchen.
2. KOT muncul dan Stock Entry diproses melalui background queue.
3. Kitchen menekan Accept.
4. Kitchen menekan Start.
5. Item ditandai Ready.
6. Captain menandai Served.
7. Recall wajib memiliki alasan.

## 6. Menangani kegagalan Stock Entry

KDS menampilkan status:

- Queued.
- Draft Created.
- Submitted.
- Failed.
- Cancelled.
- Not Required.

Restaurant Captain atau Hotel Manager dapat memakai `Post/Submit Stock`. Sistem menggunakan sync key yang sama atau revision key setelah cancellation.

Order tidak dapat menjadi Billed jika recipe Stock Entry belum submitted.

## 7. Import menu

Buka:

```text
/app/hotel-menu-import
```

Lakukan preview. Periksa semua Reject. Commit hanya setelah ERPNext Item, rate, warehouse, dan recipe benar.

Contoh `recipe_json`:

```json
[{"item_code":"ING-RICE","qty":0.2,"warehouse":"Kitchen - TBH"}]
```

## 8. UAT wajib

### KDS

- KOT baru menimbulkan indikator dan sound.
- Accept, Start, Ready, Served, Recall.
- Allergy alert terlihat jelas.
- Filter outlet, station, dan course.
- Realtime update pada dua browser.

### Inventory

- Recipe KOT membuat satu Stock Entry.
- Retry tidak menggandakan Stock Entry.
- Split bill tidak membuat Stock Entry tambahan.
- POS Invoice recipe mode memiliki `update_stock = 0`.
- Stock Entry submit menghasilkan Stock Ledger Entry.
- Cancel Stock Entry menghapus dampak ledger melalui ERPNext dan membuat reconciliation pending.
- Repost setelah cancel membuat revision key.
- Finished-goods mode tidak membuat recipe Stock Entry.

### Accounting

- Sales dan POS invoice tetap satu-satunya revenue document.
- Stock Entry tidak membuat revenue.
- Folio mirror tidak membuat General Ledger.
- Total POS/Sales Invoice sama dengan bill split.

## 9. No-Go

Jangan aktifkan Recipe Material Issue bila:

- Item bahan belum Maintain Stock.
- Warehouse salah Company.
- Stock UOM recipe belum diverifikasi.
- Invoice masih memakai update_stock pada recipe mode.
- Stock Entry queue gagal.
- Restore drill belum mencakup Stock Entry dan Stock Ledger.
