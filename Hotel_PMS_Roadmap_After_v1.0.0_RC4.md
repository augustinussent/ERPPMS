# Roadmap setelah Hotel PMS v1.0.0-rc4

## Tahap berikutnya: eksekusi, bukan fitur baru

1. Build kandidat RC4 dan pin checksum/image digest.
2. Blank-install rehearsal.
3. Upgrade rehearsal dari salinan database v0.9.0/RC sebelumnya.
4. Concurrency rehearsal untuk last room, KOT, Stock Entry dan idempotency.
5. Performance rehearsal untuk Front Desk, KDS, checkout dan API.
6. Security scan dan penetration/property-isolation test.
7. Isolated restore dan rollback drill.
8. Parallel run lintas FO, Finance, F&B, HK dan Engineering.
9. Rekonsiliasi GL, AR, tax, cashier dan Stock Ledger.
10. Sign-off delapan departemen.
11. Go/No-Go decision.
12. Build final package dari fingerprint sama.
13. Promote manifest dan deploy `v1.0.0`.
14. Verify final package checksum, image digest dan source fingerprint.

Jika satu byte executable source berubah setelah Go, buat RC baru dan ulangi gate yang terdampak.

## Setelah v1.0.0 final

Calon v1.1.0:

- Central Reservation System lintas properti.
- Housekeeping self-claim dan escalation.
- Unified application shell dan command palette.
- Read-only MCP/API expansion.
