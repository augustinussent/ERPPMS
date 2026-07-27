# Static Validation Report

Release candidate: 0.2.0

Completed outside a live Frappe bench:

- Python syntax compilation for the complete app.
- JSON parsing for DocTypes, Report, and example payloads.
- Controller class-name verification against exact Frappe DocType names.
- Child-table reference verification.
- JavaScript syntax checks with Node.js.
- Jinja syntax parsing for the confirmation-letter Print Format.
- Pure-function tests for guaranteed/actual billable pax, package units, and shifted per-night service dates.
- ZIP archive integrity check.

Not completed in this environment:

- `bench --site ... migrate` against an installed ERPNext v16 site.
- Database integration tests for MariaDB queries and transaction locking.
- Browser user-acceptance testing.
- Submission/cancellation tests for ERPNext Quotation, Sales Order, Sales Invoice, Payment Request, and Payment Entry.
- Concurrency testing with simultaneous room and function-space bookings.

A staging-site migration and full operational simulation remain mandatory before production use.
