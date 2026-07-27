# Hotel PMS ERPNext v0.9.0 — Release Notes

## Tema

Platform Hardening sebelum production gate.

## Ditambahkan

- Hotel User Property Access dan navbar property switcher.
- Query permission dan document permission pada 63 DocType operasional PMS.
- Read-only property access dan consolidated manager permission.
- Hotel Guest Property Note untuk catatan operasional per properti.
- Onboarding session yang resumable dan idempotent.
- Readiness scan, apply plan, dan configuration export.
- Migration batch, row audit, source preset, dry-run, commit, exception, dan safe rollback.
- Versioned API v1 dengan response envelope, role guard, property scope, dan idempotency key.
- OpenAPI dan Postman yang dihasilkan dari `hotel_pms/api/schema.py`.
- CI drift check untuk dokumentasi API.
- Channel-manager adapter boundary.
- HMAC webhook subscription/delivery, exponential retry, dead-letter queue, dan replay.
- HTTPS-only webhook dan SSRF private-address rejection.
- Platform console, property metrics, storage report, access review, health snapshot, worker heartbeat, dan alerts.
- Backup SHA-256 verification record.
- Privacy retention review tanpa penghapusan otomatis.
- GitHub Actions static CI, conditional real-bench runner, dan Playwright scaffold.
- Security runbook.

## Perubahan penting

`hotel_pms.api` diubah dari satu file menjadi package. Endpoint lama `hotel_pms.api.*` tetap dipertahankan melalui `hotel_pms/api/__init__.py`, sedangkan endpoint governed baru berada pada `hotel_pms.api.v1.*`.

## Default aman

- Outbound Webhooks: OFF
- Migration: wajib Dry Run
- Deposit migration: Review-only
- API write: idempotency key wajib
- Onboarding: System Manager only
- Guest retention: flag review, tidak auto-delete

## Upgrade

```bash
bench --site <site> backup
bench --site <site> migrate
bench build --app hotel_pms
bench --site <site> clear-cache
bench restart
```

## UAT minimum

### Property isolation

1. User A hanya Property A.
2. User B hanya Property B.
3. User A tidak dapat membuka URL dokumen Property B.
4. User A tidak memperoleh Property B melalui list/API/report.
5. Read Only tidak dapat write/submit/cancel.
6. Cross Property Manager hanya melihat properti yang assigned.
7. User tanpa assignment tidak melihat data operasional.

### Onboarding

8. Scan pada company valid.
9. Plan menampilkan Create/Reuse.
10. Apply dua kali tidak menduplikasi master.
11. Export config dapat dibaca JSON.
12. Hotel Manager non-System Manager ditolak.

### Migration

13. Dry run mencatat seluruh source row.
14. Duplicate menjadi Skip/Update sesuai policy.
15. Invalid row menjadi Reject dengan alasan.
16. Deposit menjadi Review.
17. Commit hanya memproses approved plan.
18. Safe rollback menolak submitted/accounting document.

### API

19. API user tanpa property ditolak.
20. Idempotency retry payload sama tidak membuat reservasi kedua.
21. Idempotency key sama payload berbeda mendapat conflict.
22. Availability memperhitungkan active group room block.
23. OpenAPI generation check lolos.

### Webhook

24. Signature receiver valid.
25. Retry terjadi pada HTTP failure.
26. Receiver retry tidak menduplikasi tindakan saat menghormati key.
27. Delivery masuk Dead Letter setelah max attempts.
28. Replay berhasil dan tercatat.
29. Private/internal target ditolak.

### Health dan recovery

30. Low-disk threshold menghasilkan warning/critical.
31. Stale worker heartbeat terdeteksi.
32. Stale backup terdeteksi.
33. Failed sync dan dead webhook terlihat.
34. Checksum backup stabil.
35. Restore drill terpisah berhasil dan RPO/RTO dicatat.

## Belum dapat dinyatakan production-ready

Rilis belum dijalankan pada bench ERPNext v16 nyata dalam environment build ini. Migration, permissions, workers, scheduler, MariaDB concurrency, outgoing network, email alert, reverse proxy, backup path, dan restore wajib diuji di staging.
