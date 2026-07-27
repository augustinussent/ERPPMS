# Hotel PMS v1.0.0-rc8: Distribution & Turnover

## Purpose

RC8 adds distribution and short-stay operational patterns without replacing ERPNext or creating a second inventory, payment, tax, accounting, or stock ledger.

The implementation borrows two useful architectural ideas:

1. Channel adapters translate provider protocols only. Availability, reservation validation, cancellation, property access, and audit remain in Hotel PMS.
2. iCal is a conservative inventory-blocking fallback, not a real-time channel-manager API and not a source of guest identity or money.

## Source of truth

| Domain | Authoritative source |
| --- | --- |
| Physical rooms, room types, restrictions, reservations | Hotel PMS operational DocTypes |
| Room availability | Existing Hotel PMS availability engine plus active distribution blocks |
| Taxes and service charges | ERPNext Sales Taxes and Charges Template through Hotel Tax Profile |
| Revenue and receivables | ERPNext Sales Invoice / POS Invoice / Accounts Receivable |
| Payments and refunds | ERPNext Payment Entry / Payment Request |
| General ledger | ERPNext GL Entry |
| Inventory and recipes | ERPNext Stock Entry / Stock Ledger Entry |
| Distribution payloads and review | Hotel Distribution Event |
| Cleaning work | Existing Hotel Housekeeping Task |

The RC8 modules do not create Sales Invoice, POS Invoice, Payment Entry, Journal Entry, Purchase Invoice, or Stock Entry.

## Provider maturity

| Provider | RC8 maturity | Capability |
| --- | --- | --- |
| Generic iCal | Shipped | Exact-room feed import and tokenized blocks-only feed export |
| Generic JSON | Shipped | HMAC-signed inbound book/modify/cancel contract and normalized ARI seam |
| Channex | Adapter | Configuration and protocol boundary only; live activation blocked |
| STAAH | Adapter | Configuration and protocol boundary only; live activation blocked |
| AioSell | Adapter | Configuration and protocol boundary only; live activation blocked |
| Custom | Adapter | Development seam only; live activation blocked |

A provider name in a dropdown is not evidence of a certified integration. RC8 deliberately refuses to mark uncertified adapters Live.

## DocTypes

### Hotel Distribution Connection

Property-scoped connection and health record. It stores encrypted endpoint/API/webhook credentials, sync policy, feed slug/hash, last test/sync/push result, failure count, and maturity status.

### Hotel Distribution Room Mapping

Maps one external room or room type to Hotel Room, Hotel Room Type, and optional Hotel Rate Plan. Generic iCal requires exactly one `Room` mapping because iCal inventory is property-unit specific and cannot safely infer pooled room-type inventory.

### Hotel Distribution Event

Operational inbox/outbox record for calendar blocks, inbound bookings, modifications, cancellations, acknowledgements, and ARI pushes. It stores payload hash, idempotency key, external reference, processing result, and links to Hotel Reservation. It is not a financial ledger.

### Hotel Prearrival Form Template / Question / Submission

Property-scoped form builder and one-time reservation response. Labels and values are snapshotted at submission time so later template edits do not rewrite historical answers.

## Secure iCal

### Import

The server validates the URL before every fetch:

- HTTPS only.
- No URL credentials.
- Standard HTTPS port only.
- DNS resolution must return public addresses.
- Private, loopback, link-local, multicast, and reserved addresses are rejected.
- Redirects are not followed.
- Timeout is enforced.
- Response size is capped at 2 MiB.
- Calendar/plain-text content type is required.

The parser observes all-day iCal semantics: `DTEND` is exclusive. A stay ending on 12 August frees the room on 12 August; touching stays are normal turnover, not a conflict.

Events are deduplicated by connection, UID, and dates. Generic host blocks such as `Reserved`, `Blocked`, and `CLOSED - Not available` are treated as blocks, not guest names. Exact cross-feed echoes can be classified as likely echoes while partial overlaps remain reviewable conflicts.

### Export

The exported feed contains only:

- Stable opaque UID.
- DTSTART and exclusive DTEND.
- `SUMMARY:Blocked`.

It never exports guest name, email, phone, price, notes, reservation source, or financial information.

The feed uses a durable random slug plus a high-entropy token stored only as SHA-256. Token comparison is constant-time. Requests are rate-limited per source IP and returned with no-cache headers.

### Sync cadence

The scheduler runs every 15 minutes, but each connection respects its configured `sync_interval_minutes`, with a minimum of five minutes. A failing connection does not stop other properties from syncing.

## Generic JSON distribution webhook

Endpoint:

```text
/api/method/hotel_pms.distribution.distribution_webhook?connection=<connection-name>
```

Required header:

```text
X-Hotel-Distribution-Signature: sha256=<HMAC-SHA256 raw-body>
```

Normalized events:

```text
book
modify
cancel
```

Required booking fields:

```text
external_reference
external_room_id
arrival_date
 departure_date
room_rate_total
```

Optional fields include guest name, email, phone, adults, children, gross total, currency, channel, and notes.

### Booking safeguards

- External reference is unique within property and connection.
- Room mapping is property-scoped.
- Availability is checked against Hotel PMS reservations, room blocks, group holds, and iCal distribution blocks.
- External sell price is preserved as an operational snapshot and converted into an exact per-night Decimal rate.
- Mapping price basis must be `Room Rate Total`.
- A different external currency is held in `Needs Review`; it is never interpreted as the property currency.
- The resulting Hotel Reservation uses the existing submission and lifecycle hooks.
- No invoice, payment, tax row, journal, or stock entry is created by the webhook.

### Modification and cancellation

Modifications are stored as `Needs Review`; RC8 does not silently alter dates, rooms, or rates after an OTA change. Cancellation invokes the existing governed cancellation path after HMAC verification and external-reference matching.

## ARI seam

ARI snapshots are built from the same availability and pricing services used by Hotel PMS. Room blocks, group holds, reservations, and distribution blocks are netted from availability. Provider adapters receive normalized availability/rate/restriction data and cannot override domain calculations.

Channex, STAAH, and AioSell remain Adapter maturity until provider credentials, field mappings, certification cases, webhook signatures, retries, and production evidence are completed.

## Controlled check-in

The Front Desk check-in action now loads one context containing:

- Registration status.
- ID and address-proof readiness.
- Pre-arrival form status.
- Allergies and accessibility notes.
- Assigned room and housekeeping state.
- Sellable alternatives of the same room type.
- Deterministic recommendation with a reason.

The final action still calls the existing Hotel Reservation check-in method. A selected replacement room must belong to the same property and room type, remain available, and be Clean or Inspected. Dirty or blocked rooms cannot be handed over through the controlled flow.

## One-time pre-arrival forms

Staff issues one active form per reservation/template. The URL contains a random raw token shown to staff once; only its SHA-256 hash is stored.

The public form:

- Is scoped to one reservation and one purpose.
- Can be submitted once.
- Validates required fields before consuming the token.
- Uses a database row lock during submission.
- Snapshots field ID, type, label, and value.
- Stores answer SHA-256 and source-IP hash.
- Does not accept prices, payments, or accounting instructions.

Submitted answers are retained according to the property privacy policy. An unsubmitted link can be revoked.

## Occupant identity documents

Registered occupants can store their own private ID file. Replacement uses the same sanitizing private-file pipeline as primary guest documents. Retention purge removes occupant scans together with the reservation’s other identity documents under the configured Verify-and-Discard policy.

OCR from RentTools was not copied. Cloud OCR would transmit identity data to a third party and therefore requires a separate data-processing agreement, explicit configuration, consent/legal basis, retention policy, and Production Gate. RC8 keeps capture local and private.

## Turnover planner

Operational page:

```text
/app/hotel-turnover-planner
```

The planner derives work from active Hotel Reservations and existing Housekeeping configuration. It calculates:

- Checkout-to-next-check-in minutes.
- Same-day turnover risk.
- Target-ready time.
- Priority.
- Default and backup assignee conflicts.
- Unassigned or overlapping cleaning work.

Creating work uses the existing `Hotel Housekeeping Task` and deterministic operation keys. Re-running the planner does not create a second task for the same reservation/room/date.

## Production Gate

RC8 adds:

```text
DISTRIBUTION_READINESS
PREARRIVAL_SECURITY
TURNOVER_READINESS
```

Promotion is blocked when:

- An enabled distribution connection failed its test or is improperly marked Ready/Live.
- A mapping points outside its property.
- A Generic iCal connection lacks an exact-room mapping or feed token.
- An inbound event is Failed or Needs Review.
- An active pre-arrival submission lacks a one-time token contract.
- A high-risk turnover has no corresponding housekeeping task.

## Bench validation

```bash
cd ~/frappe-bench
SITE=hotel-staging.example.com \
BENCH_ROOT="$PWD" \
apps/hotel_pms/ci/run_rc8_bench_smoke.sh
```

The smoke script migrates, seeds RC8 setup, checks required DocTypes, and proves that setup changes no Sales Invoice, POS Invoice, Payment Entry, Journal Entry, Purchase Invoice, Stock Entry, GL Entry, or Stock Ledger Entry counts.

## Known limitations

- iCal remains eventually consistent and cannot provide real-time OTA inventory guarantees.
- Channex, STAAH, and AioSell are not certified or live in RC8.
- OTA modifications require manual review.
- Multi-currency distribution requires a governed conversion workflow that is not included in RC8.
- No real Frappe/ERPNext v16 bench was available in the build environment used to package RC8.
