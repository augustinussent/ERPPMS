# Front Office Release v0.4.0

## Scope

Release 0.4.0 implements the first operational front-office layer on top of the existing ERPNext-integrated PMS foundation.

### Delivered

- `Hotel Front Desk` page with arrivals, departures, in-house stays, no-show review count, outstanding balance estimate, and room-state summary.
- 14-day tape chart for physical rooms and active stays.
- Quick multi-room booking with one idempotent reservation transaction.
- Controlled room move for checked-in stays.
- Controlled extend-stay and early-departure actions.
- Immutable `Hotel Stay Change Log` records for room/date changes.
- Cancellation and no-show policy engine.
- Cancellation/no-show confirmation record and print format.
- Guest Registration Card and registered occupant table.
- Optional verified-GRC requirement before check-in.
- Draft ERPNext Payment Entry creation for deposits and refunds.
- Payment Entry linkage to Hotel Reservation and automatic submitted-total refresh.
- Aggregate room-type inventory validation for multi-room bookings.
- Check-in readiness guard for operational and housekeeping status.

## Access

Open:

```text
/app/hotel-front-desk
```

Roles:

- System Manager
- Hotel Manager
- Front Desk
- Night Auditor

## Required master configuration

1. Create at least one `Hotel Cancellation Policy`.
2. Map its fee item to a non-stock ERPNext service Item.
3. Set the policy on `Hotel Property` or `Hotel PMS Settings`.
4. Configure a default Account for every used ERPNext Mode of Payment and Company.
5. Decide the default guest-ID retention mode.
6. Keep automatic no-show processing disabled until UAT is approved.
7. Keep verified-GRC enforcement disabled until Front Office has completed training.

## Controlled transaction rule

Do not change reservation status manually. Use the supplied actions for:

- Check-in
- Check-out
- Cancellation
- No-show
- Room move
- Extend stay
- Early departure

Direct cancellation of the submitted reservation document is blocked. A cancellation changes the operational status while preserving the submitted reservation as the original commercial record.

## Deposit and refund accounting

A deposit or refund button creates a **draft ERPNext Payment Entry**. Finance or an authorized user must verify and submit it. Only submitted Payment Entries contribute to `Deposit Received` and `Deposit Refunded` on the reservation.

The PMS does not create a separate cash ledger. ERPNext remains authoritative for cash, bank, receivables, advances, and refunds.

## UAT minimum

1. Create a two-room booking and repeat the same request key; only one reservation may exist.
2. Attempt a multi-room booking when only one unheld room remains; the transaction must fail completely.
3. Check in a dirty room; the action must be blocked.
4. Move a checked-in guest to a clean room; old room becomes Dirty and receives one cleaning task.
5. Repeat the same room-move request key; no second change log or cleaning task may appear.
6. Extend a stay into an occupied future date; the action must fail.
7. Shorten a stay and verify the change log.
8. Cancel inside and outside the free-cancellation window.
9. Waive a fee as Front Desk when manager approval is required; access must be denied.
10. Process no-show twice with the same key; only one cancellation record and one fee charge may exist.
11. Create, submit, cancel, and recreate a deposit Payment Entry; reservation totals must follow submitted ERPNext documents.
12. Generate and print Guest Registration Card and cancellation confirmation.
13. Enable verified-GRC enforcement and confirm that unverified registration blocks check-in.
14. Run night audit after cancellation/no-show and confirm no room-night charge is posted for the cancelled stay.

## Known limitations

- Tape chart is operational and clickable but does not yet support drag-and-drop.
- Room upgrades to a different room type require a future rate-approval workflow.
- Deposit allocation to Sales Invoice still uses ERPNext's standard advance allocation/reconciliation tools.
- Unified checkout across several invoices is not yet implemented.
- Indonesian hotel tax and service-charge policy requires configuration and further validation.
- This release has static and pure-rule tests but still requires execution on a real Frappe/ERPNext v16 staging bench.
