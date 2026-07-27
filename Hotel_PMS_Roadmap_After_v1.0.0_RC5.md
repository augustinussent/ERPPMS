# Roadmap setelah Hotel PMS v1.0.0-rc5

## Tidak ada RC berikutnya tanpa temuan

1. Deploy RC5 pada staging Frappe/ERPNext v16 yang versinya dipin.
2. Jalankan `ci/run_staging_execution.sh`.
3. Selesaikan blank-install dan upgrade rehearsal.
4. Jalankan concurrency, security, performance, restore, dan rollback rehearsal.
5. Jalankan parallel run hotel minimal satu siklus operasional yang disepakati.
6. Rekonsiliasi GL, AR, pajak, kasir, POS, dan Stock Ledger.
7. Perbaiki blocker. Setiap perubahan executable menghasilkan RC baru.
8. Dapatkan sign-off delapan departemen.
9. Ambil keputusan Go.
10. Promosikan fingerprint yang sama menjadi v1.0.0 final.

Setelah v1.0.0 final, barulah pengembangan v1.1.0 dapat dimulai: Central Reservation System lintas properti, Housekeeping self-claim, unified application shell, dan read-only MCP.
