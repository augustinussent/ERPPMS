# Roadmap setelah Hotel PMS v1.0.0-rc2

## Production gate tetap wajib

v1.0.0-rc2 tidak menggantikan v1.0 Production Gate. Blank install, upgrade rehearsal, accounting reconciliation, concurrency, security, performance, restore drill, parallel run, dan departmental sign-off tetap harus diselesaikan sebelum tag final production.

## v1.2.0 F&B Operational Depth

- KDS v2: accept/start, station/course, sound, aging, allergy warning, item progress, dan recall.
- ERPNext-native recipe mapping menggunakan Item, Warehouse, dan BOM/custom recipe mapping.
- KOT fire membuat satu idempotent ERPNext Stock Entry/Material Issue.
- Void setelah KOT fire dicatat sebagai wastage, bukan reversal otomatis.
- Menu, ingredient, recipe, dan laundry-rate bulk import dengan dry-run preview.
- Stock variance dan wastage report dari ERPNext Stock Ledger.

## v1.3.0 Chain Operations

- Central Reservation System lintas properti yang diizinkan.
- Alternate-property suggestion.
- Cross-property quote dan booking.
- Portfolio position dashboard.

## v1.4.0 Workforce & UX

- Housekeeping self-claim, accept/decline, dan multi-level escalation.
- Floor minibar/laundry posting melalui jalur folio yang sama.
- Unified application shell dan command palette.

Tidak ada release yang boleh memperkenalkan accounting ledger atau stock ledger tandingan.

## Kandidat berikutnya

Lanjutkan sebagai `v1.0.0-rc3`, bukan v1.2.0, untuk KDS v2 dan ERPNext-native recipe Stock Entry.
