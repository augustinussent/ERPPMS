# Roadmap after Hotel PMS v1.0.0-rc8

## Immediate: RC8 staging validation

- Fresh install and RC7-to-RC8 upgrade rehearsal.
- Exact-room iCal import/export and token-rotation tests.
- Generic JSON signed booking replay/concurrency tests.
- Room mapping and foreign-currency review tests.
- Check-in and pre-arrival public security tests.
- Turnover/housekeeping idempotency tests.
- GL, AR, tax, cashier, POS, recipe stock, and distribution reconciliation.
- Restore and rollback drill.
- Eight departmental sign-offs.

No RC9 is needed unless executable source changes.

## v1.1.0 after v1.0.0 final

### Certified distribution

- Complete one provider certification, preferably Channex or the hotel’s selected channel manager.
- Durable outbound queue with per-item acknowledgement and replay.
- OTA modification comparison/approval workspace.
- Provider reconciliation and inventory drift report.
- Currency conversion policy using ERPNext Currency Exchange, without parallel accounting.

### Short-stay operations

- Housekeeping staff capacity calendar and backup assignment rules.
- Turnover SLA forecasting using actual cleaning history.
- One-time guest-form response mapping into approved reservation/profile fields.
- Data portability export covering distribution and pre-arrival records.

### Governance

- Provider credential rotation evidence.
- Automated SSRF regression and webhook replay suite.
- Integration contract tests on real Frappe/ERPNext bench in CI.

## Explicitly deferred

- Cloud passport OCR until legal basis, consent, DPA, vendor retention, and data-residency controls are approved.
- Automatic foreign-currency reinterpretation.
- Automatic OTA modification acceptance.
- Autopilot rate changes.
- Any distribution-owned invoice, payment, tax, or stock ledger.
