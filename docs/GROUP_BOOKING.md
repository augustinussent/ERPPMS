# Group Booking, Meeting Packages, BEO, and Confirmation Letter

This module treats a group as one commercial and operational umbrella rather than a pile of unrelated room reservations.

## Implemented sequence

### 1. Group booking and lifecycle

`Hotel Group Booking` stores the customer, PIC, stay dates, event dates, estimated/guaranteed/actual pax, commercial references, room blocks, participants, functions, packages, billing rules, deposit schedule, and confirmation-letter text.

Status flow:

```text
Inquiry → Tentative → Confirmed → Event Active → Completed → Closed
                     ↘ Cancelled
```

Submitting an Inquiry or Tentative booking changes it to Confirmed, creates an ERPNext Project, and creates the master Group Folio.

### 2. Room block and rooming list

`Hotel Group Room Block` holds room-type inventory without prematurely assigning room numbers. `Hotel Group Participant` becomes the rooming list.

Availability calculation uses:

```text
operational rooms
- overlapping individual reservations
- outstanding room blocks from other groups
= room-type capacity available to this group
```

Assigned rooms are counted once, even when two participants share the same room. At cut-off, only the unassigned balance is released. Exact-room reservations can be generated from the rooming list after the group is confirmed.

### 3. Function-space availability

`Hotel Function Space` stores setup capacities and setup/breakdown buffers. Event functions validate:

- date/time order;
- property ownership;
- room enabled status;
- setup-specific capacity;
- overlap against another blocking group booking.

### 4. Meeting package templates

`Hotel Package Template` contains:

- ERPNext package sales Item;
- package type;
- minimum pax;
- rates by occupancy and pricing basis;
- included components and revenue allocation.

Supported pricing bases:

- Per Person Per Day
- Per Person Per Night
- Per Person Package
- Per Room Per Night
- Flat

Supported component frequencies:

- Once
- Per Day
- Per Night

The included component allocation must total 100%, or all components may be left at zero for equal allocation.

### 5. ERPNext Quotation and Sales Order

Buttons on Group Booking create an ERPNext Quotation and Sales Order using package sales Items. The Group Booking reference is stored in custom fields. These documents represent the commercial offer and contract.

Operational package components are invoiced from the Group Folio. They are deliberately separate from the Sales Order package line, so production rollout must decide whether Sales Orders are closed administratively or mapped to component-level billing.

The deposit schedule supports percentage or fixed-amount milestones and links each milestone to ERPNext Payment Request and Payment Entry records.

### 6. Banquet Event Order

`Hotel Banquet Event Order` copies the current function schedule, guaranteed pax, menus, equipment, special requirements, and billing instructions. Each generated document increments the revision number. Submitting the latest BEO marks older submitted versions as Superseded.

### 7. Group folio and charge routing

`Hotel Group Folio` is the operational subledger. Charges may route to:

- Master Folio
- Individual Folio
- Direct Bill

Billing instructions may split a category by percentage, and rows for a specific category override the general `Package` route. Charges are grouped by Billing Customer when Sales Invoices are created. One Group Folio can therefore create multiple ERPNext Sales Invoices.

### 8. Guaranteed and actual pax

Billable pax follows:

```text
max(Guaranteed Pax, Actual Pax)
```

Before either value is entered, Estimated Pax is used for quotations and planning.

### 9. Package schedule and night audit

The schedule generator expands package components into dated `Hotel Package Posting` records. Regeneration replaces unposted rows but preserves posted rows using idempotency keys.

The standard hotel night audit now also posts due group-package components to the Group Folio. Manual posting remains available for supervisors.

### 10. Profitability

The `Hotel Group Profitability` report compares:

- contracted package value;
- submitted Sales Invoice revenue;
- outstanding receivables;
- submitted Purchase Invoice direct costs;
- gross contribution and margin.

Tag Purchase Orders and Purchase Invoices with the Group Booking to make event costs visible.

## Confirmation letter

The app creates the `Hotel Group Confirmation Letter` Print Format during installation or migration. Group Booking provides editable fields for:

- letter date;
- addressee;
- subject;
- opening paragraph;
- terms and conditions;
- signatory name and title.

The form has buttons for browser print view and direct PDF. The letter automatically includes room blocks, function schedule, package pricing, package total, required deposit, and special requirements.

## Operational order

1. Create the customer and contact in ERPNext.
2. Create Group Booking as Inquiry.
3. Add room blocks, functions, packages, and preliminary pax.
4. Check availability.
5. Set Tentative and specify Hold Until.
6. Create and send Quotation.
7. Enter deposit requirement and confirmation-letter terms.
8. Submit the Group Booking to confirm it.
9. Create Sales Order and issue the Confirmation Letter.
10. Complete the rooming list and assign rooms.
11. Generate participant reservations.
12. Create and submit the current BEO revision.
13. Finalize guaranteed pax.
14. Generate the package schedule.
15. During the event, update actual pax and service status.
16. Night audit or supervisor posts due package components.
17. Add approved extras to the Group Folio and route them correctly.
18. Create Sales Invoice(s), allocate customer advances, and collect the balance.
19. Tag direct Purchase Invoices to the Group Booking.
20. Review profitability, complete the event, then close the booking.
