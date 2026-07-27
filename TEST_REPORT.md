# Hotel PMS ERPNext v1.1.0 Test Report

## Scope

Static and pure-rule validation for the Localization & Communication adoption release. This report does not claim that a live Frappe/ERPNext v16 bench, MariaDB, Redis, background workers, Meta Cloud API, or accounting ledger was executed in the build environment.

## Results

- Python files parsed/compiled: 352
- JavaScript files syntax-checked: 55
- JSON files parsed: 138
- DocTypes audited: 105
- Desk pages: 15
- Property-scoped DocTypes checked: 66
- Pure-rule tests: 39 passed
- DocType/property contract errors: 0
- v1.1 financial/stock creation contract errors: 0
- OpenAPI documentation drift: 0
- Shell syntax errors: 0

## v1.1 invariants checked

- ERPNext Company remains authoritative for property country, default currency, and tax ID.
- Localization and communication modules do not create Sales Invoice, POS Invoice, Payment Entry, Journal Entry, Purchase Invoice, or Stock Entry.
- Localization modules do not append ERPNext tax rows.
- Individual and city-ledger invoice flows resolve one tax profile to one ERPNext Sales Taxes and Charges Template.
- Group invoicing separates charges by billing customer and tax profile.
- WhatsApp outbound rows use unique idempotency keys and asynchronous delivery.
- Meta inbound rows use provider-derived idempotency keys.
- Inbound reservation matching is restricted to the channel connection property.
- Guest files are private, re-encoded, dimension-limited, replace-in-place, and limited to pre-check-in status.

## Required real-bench gates

- Blank install and upgrade migration from the previous database copy.
- ERPNext Company, Account, Tax Template, and currency validation.
- Quote-to-submitted-Sales-Invoice tax reconciliation.
- GL, Accounts Receivable, Payment Entry, and tax reconciliation.
- Group invoice separation with real ERPNext taxes.
- Meta webhook verification, HMAC callback, retry, duplicate delivery, and dead-letter replay.
- Worker outage and Meta outage during booking/payment-request creation.
- MariaDB concurrent queue and invoice tests.
- Property permission tests through Desk, API, and reports.
- Private-file backup, isolated restore, access control, and Verify-and-Discard deletion.

## Conclusion

The source passes static and pure-rule release checks. Production approval remains blocked until the environment-specific Production Gate and departmental sign-offs are completed.
