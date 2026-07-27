# Hotel PMS ERPNext v1.0.0-rc2
## Localization & Communication Adoption

### Fitur

- Country-pack registry dengan Generic dan Indonesia pack.
- ERPNext Company menjadi sumber country, currency, dan tax ID properti.
- Validasi Hotel Tax Profile terhadap ERPNext Company, Account, dan Sales Taxes and Charges Template.
- Pencegahan campuran tax profile dalam satu folio invoice.
- Group invoice otomatis dipisahkan berdasarkan customer dan tax profile.
- WhatsApp Meta Cloud API per properti.
- Async and idempotent template/text delivery, retry, callback, dan dead-letter state.
- Communication inbox serta inbound-to-maintenance action.
- Private guest ID/address proof upload dengan sanitasi, replacement, dan retention purge.
- Halaman `/app/hotel-communications`.
- CI contract guard untuk memastikan modul adopsi tidak membuat dokumen keuangan atau stok.

### Batas akuntansi

Rilis ini tidak menambahkan ledger PMS baru. Semua pajak dan service charge pada invoice berasal dari ERPNext Sales Taxes and Charges Template. Seluruh Sales Invoice, POS Invoice, Payment Entry, Purchase Invoice, Journal Entry, dan Stock Entry tetap dibuat oleh workflow ERPNext yang sudah ada.

### Belum diadopsi

- Custom ingredient stock ledger Kamra.
- Tarif PBJT otomatis.
- MCP/AI write actions.
- KDS v2 dan recipe consumption. Keduanya direncanakan pada v1.2.0 dengan ERPNext Stock Entry sebagai satu-satunya posting stok.

### Wajib diuji di staging

- Migration dan patch.
- Quote versus submitted Sales Invoice.
- Group invoice split berdasarkan tax profile.
- GL dan Accounts Receivable reconciliation.
- Meta webhook verification, signature, retry, dan duplicate callback.
- Booking ketika Meta outage.
- Property access isolation.
- Private file backup/restore dan Verify-and-Discard purge.
