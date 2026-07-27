# Hotel PMS v0.6.0 — Revenue and Billing

## 1. Purpose

Version 0.6.0 adds controlled pricing, commercial approvals, folio movement, corporate credit, payment links, cashier reconciliation, travel-agent commission, and a configurable hotel tax/service-charge layer while keeping ERPNext as the official accounting ledger.

The PMS calculates and records hotel-operational intent. ERPNext remains authoritative for Customer, Supplier, Item, Sales Invoice, Purchase Invoice, Payment Entry, Payment Request, accounts receivable, accounts payable, tax posting, cash/bank balances, and general ledger.

## 2. New operational pages

- `/app/hotel-revenue-calendar` — edit rate overrides and restrictions by date.
- `/app/hotel-checkout` — unified guest checkout and billing screen.
- `/app/hotel-cashier` — open, operate, reconcile, and close cashier shifts.

## 3. Rate engine

Pricing resolution order:

1. Base rate plan.
2. Derived-plan adjustment and meal supplement.
3. Highest-priority matching season and weekday rule.
4. Date-level calendar override.
5. Optional manually requested rate.
6. Floor-rate approval when required.
7. Voucher discount.
8. Configured service charge and tax calculation.

Supported controls:

- Minimum and maximum stay.
- Closed to arrival.
- Closed to departure.
- Stop sell.
- Minimum and maximum advance booking days.
- Floor rate.
- Rate approval with expiry.
- Rate quote hash for audit and stale-quote detection.

A rate quote is deterministic. Language-model or UI suggestions must never calculate money independently.

## 4. Rate setup sequence

1. Create the base `Hotel Rate Plan`.
2. Create optional derived plans linked through `Base Rate Plan`.
3. Create `Hotel Rate Season` records and select applicable weekdays.
4. Use Hotel Revenue Calendar for exceptional date overrides and restrictions.
5. Configure floor rates and approval requirements.
6. Test quotes for normal, seasonal, closed, minimum-stay, and below-floor scenarios.

## 5. Voucher workflow

A `Hotel Voucher` can be restricted by:

- Property.
- Booking dates.
- Stay dates.
- Room type.
- Rate plan.
- Customer.
- Minimum stay.
- Total usage.
- Usage per customer.
- Maximum discount.

The reservation stores a `Hotel Voucher Redemption`. Submission reserves one redemption. Cancellation releases it. The discount is posted to the folio through the configured non-stock voucher-discount Item.

## 6. Travel-agent workflow

1. Create the travel agent as an ERPNext Supplier.
2. Create a `Hotel Travel Agent Contract` with validity, commission, pricing basis, commission Item, expense account, and cost center.
3. Select the contract on the reservation.
4. Checkout accrues the commission status as pending.
5. Build a `Hotel Travel Agent Settlement` for a date range.
6. Create a duplicate-safe ERPNext Purchase Invoice draft.
7. Submit and pay the Purchase Invoice through ERPNext.
8. Daily reconciliation marks the settlement and reservations paid when outstanding becomes zero.

## 7. Hotel Tax Profile

The profile can define:

- Service-charge percentage.
- Tax percentage.
- Tax basis.
- Whether advertised rates include service charge.
- Whether advertised rates include tax.
- Rounding method.
- ERPNext Sales Taxes and Charges Template.

The PMS tax breakdown is an operational estimate and display. The linked ERPNext tax template controls actual accounting entries. A qualified accountant must confirm the profile and template before go-live.

## 8. Folio split and transfer

The checkout page can move selected uninvoiced charges between:

- Guest folios.
- Group folios.
- City-ledger folios.

The original row is voided, and replacement rows are created for the remainder and destination. The system verifies exact amount conservation and records an immutable `Hotel Folio Transfer`. Reversal is allowed only while generated rows remain uninvoiced and untouched.

Never edit transferred rows directly. Reverse the transfer, then perform the corrected transfer.

## 9. Unified checkout

The checkout screen shows:

- Active and void charges.
- Uninvoiced charges.
- Sales Invoices and outstanding balances.
- Available customer advances/deposits.
- Payment Requests.
- Direct-bill approval.
- Charge transfer controls.
- Final checkout action.

Recommended order:

1. Review charges.
2. Transfer or split company/personal charges.
3. Create Sales Invoice drafts.
4. Submit invoices in ERPNext.
5. Apply available advance payments.
6. Collect or direct-bill the remaining balance.
7. Confirm zero payable balance or valid credit approval.
8. Complete checkout.

## 10. Payment Request

A payment request can only be created from a submitted Sales Invoice with outstanding balance. The PMS uses a deterministic sync key and returns an existing active request instead of creating another one for the same invoice and gateway.

The actual payment URL depends on a correctly configured ERPNext Payment Gateway Account and the `payments` app/provider setup.

## 11. City ledger and direct bill

`Hotel City Ledger Account` maps directly to one ERPNext Customer and stores the operational credit policy.

Direct billing requires:

- An active account.
- A request and approval.
- Approved amount sufficient for the intended balance.
- Current submitted ERPNext receivables plus the new amount within the configured credit limit.

City-ledger folios can create Sales Invoice drafts for the mapped Customer. ERPNext remains the accounts-receivable source of truth.

## 12. Cashier shift

A cashier shift maps to an ERPNext Mode of Payment and its company default account.

The shift reconciles:

- Submitted ERPNext Payment Entries assigned to the shift.
- Submitted POS Invoice payment rows assigned to the shift.
- Controlled drawer movements.
- Opening float.
- Counted closing cash.
- Expected cash and variance.

A variance reason is mandatory when the count differs. Variance above the configured threshold moves the shift to `Closing Review` unless closed by Hotel Manager, Accounts Manager, or System Manager.

No separate accounting journal is created by closing a shift. Accounting entries remain the submitted ERPNext documents.

## 13. Required master data

Before UAT configure:

- ERPNext Company and chart of accounts.
- Hotel Property and cost center.
- Room Revenue and voucher-discount Items.
- Tax and service-charge accounts/templates.
- Mode of Payment and company account mapping.
- Payment Gateway Account if online links are used.
- Supplier and commission expense setup for travel agents.
- Customer and payment terms for city-ledger accounts.
- Rate plans, seasons, vouchers, and tax profiles.

## 14. Minimum UAT

1. Normal base-rate quote.
2. Derived-plan quote.
3. Season weekday inclusion and exclusion.
4. Calendar override.
5. Stop-sell denial.
6. CTA and CTD denial.
7. Minimum and maximum stay denial.
8. Advance-booking restriction denial.
9. Below-floor request without approval denial.
10. Approved below-floor rate.
11. Voucher valid, expired, over-limit, and duplicate retry.
12. Travel-agent commission calculation.
13. Travel-agent settlement and Purchase Invoice retry.
14. Tax-inclusive and tax-exclusive quote comparison.
15. Full and partial folio transfer.
16. Transfer reversal before invoicing.
17. Reversal denied after invoicing.
18. Payment Request duplicate retry.
19. Direct bill within and above credit exposure.
20. Cashier opening, receipt, refund, drawer movement, and closing.
21. Cashier variance below threshold.
22. Cashier variance above threshold requiring manager review.
23. Sales Invoice cancel and folio row release.
24. Payment Entry cancel and cashier/deposit recalculation.
25. End-to-end accounting reconciliation with zero unexplained difference.

## 15. Known limitations

- No OTA/channel-manager rate distribution.
- No drag-based mass rate update.
- No automatic dynamic pricing forecast.
- Payment links require an external supported gateway configuration.
- Tax profiles are configurable, not a substitute for current legal/accounting advice.
- Cashier shift does not yet lock a formal night-audit business date.
- Full automated bench, concurrency, permissions, browser, migration, payment-gateway callback, and accounting tests remain required.
