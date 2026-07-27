# Roadmap setelah Hotel PMS v1.0.0-rc3

## Prioritas berikutnya: Production Gate execution

Tidak disarankan menambah modul besar sebelum RC3 dijalankan pada bench ERPNext v16 nyata.

Urutan:

1. Blank install rehearsal.
2. Upgrade rehearsal dari v0.9.0 dan rc2.
3. Restaurant recipe Stock Entry reconciliation.
4. POS/Sales Invoice stock-policy reconciliation.
5. MariaDB concurrency untuk KOT dan Stock Entry.
6. Performance test KDS realtime.
7. Security dan permission test.
8. Backup serta isolated restore drill.
9. Parallel run Front Office, F&B, Finance, HK, dan Engineering.
10. Departemental sign-off.

Setelah semua blocker lulus, kandidat dapat dipromosikan menjadi `v1.0.0` final tanpa perubahan kode. Bila ada perubahan kode, gate terkait harus diulang.

## Setelah v1.0.0 final

Calon roadmap `v1.1.0` sebenarnya:

- Central Reservation System lintas properti.
- Housekeeping self-claim dan multi-level escalation.
- Unified application shell dan command palette.
- Expanded API dan read-only MCP.
