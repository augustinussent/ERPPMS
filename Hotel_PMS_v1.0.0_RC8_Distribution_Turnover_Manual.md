# Hotel PMS ERPNext v1.0.0-rc8
## Distribution & Turnover Implementation Manual

## 1. Release status

`v1.0.0-rc8` is a staging release candidate. It supersedes RC7 because distribution, iCal, pre-arrival, check-in, and turnover executable code was added.

Do not promote RC7 after installing RC8 evidence. The release manifest, ZIP checksum, image digest, and normalized source fingerprint must all identify RC8.

## 2. Upgrade

```bash
cd ~/frappe-bench
bench --site hotel-staging.example.com backup --with-files
```

Install or replace the application source with the RC8 archive, then:

```bash
bench --site hotel-staging.example.com migrate
bench build --app hotel_pms
bench --site hotel-staging.example.com clear-cache
bench restart
```

Verify:

```bash
bench --site hotel-staging.example.com execute hotel_pms.distribution_ci.run_rc8_bench_smoke
```

## 3. Distribution configuration

### 3.1 Generic iCal

Create `Hotel Distribution Connection`:

```text
Provider: Generic iCal
Maturity: Shipped
Enabled: initially disabled
Endpoint: platform export URL, HTTPS only
Sync interval: 15 minutes or more
Inbound booking: disabled
Outbound ARI: disabled
Buffer before/after: according to hotel policy
```

Create exactly one enabled `Hotel Distribution Room Mapping`:

```text
Mapping Mode: Room
Room: exact Hotel Room
Room Type: matching Hotel Room Type
External Room ID: stable platform/listing identifier
Incoming Price Basis: Room Rate Total
```

Run **Test Connection**. Only after a successful test should the connection be enabled and marked Ready/Live.

Rotate the public feed token and copy the generated URL to the OTA calendar-import screen. The URL is a secret because anyone possessing it can read blocked dates. It contains no guest identity or price, but it still reveals occupancy patterns.

### 3.2 Generic JSON

Create a connection with:

```text
Provider: Generic JSON
Maturity: Shipped
Enabled: initially disabled
Inbound Booking Enabled: enabled after UAT
Webhook Secret: high-entropy random secret
External Property ID: provider-side property identifier
```

Create all room/rate mappings, run **Test Connection**, execute signed webhook tests, and verify external-reference duplicate handling before marking Ready/Live.

Signature example:

```python
import hashlib, hmac, json
body = json.dumps(payload, separators=(",", ":")).encode()
signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
```

Use the exact raw HTTP body for verification. Re-serializing JSON before HMAC calculation changes the signature.

### 3.3 Channex, STAAH, AioSell

These remain Adapter maturity. RC8 blocks `Live` status. Certification must prove:

- Connection authentication.
- Room and rate-plan mapping.
- Availability/rate/restriction payloads.
- Booking create/duplicate/modify/cancel.
- Currency and tax interpretation.
- Webhook signing and replay prevention.
- Timeout, retry, dead-letter, and alert behavior.
- Property isolation.
- Provider reconciliation.

Do not enter production credentials merely to make the screen look complete. Software has enough ceremonial configuration already.

## 4. Check-in flow

From `/app/hotel-front-desk`, use **Check In**. The dialog displays registration, documents, pre-arrival answers, room readiness, and alternatives.

A room can be selected only when:

- It belongs to the same property.
- It matches the reserved room type.
- It is operationally Available.
- Housekeeping status is Clean or Inspected.
- It does not overlap another reservation or distribution block.

The final operation calls the existing reservation check-in lifecycle; it does not bypass policy, deposit, registration, or room-state rules.

## 5. Pre-arrival forms

Create an enabled `Hotel Prearrival Form Template` per property. Questions can be short text, long text, number, date, time, select, multi-select, yes/no, phone, or email.

Suggested non-financial questions:

- Estimated arrival time.
- Transfer requirement.
- Dietary/allergy information.
- Accessibility requirement.
- Bed or floor preference.

From a Tentative or Confirmed reservation, choose **Issue Pre-arrival Form**. Copy the generated URL immediately; the raw token is not recoverable later.

Never ask the guest to enter card number, CVV, bank password, tax calculation, or refund instruction in this form.

## 6. Turnover planner

Open:

```text
/app/hotel-turnover-planner
```

Review same-day turnover windows and assignment conflicts. Creating tasks uses the existing Housekeeping Task, not a separate cleaning ledger.

Before go-live, test:

- Same-day checkout/check-in.
- Late checkout.
- Early arrival.
- Dirty/Out of Order room.
- Default cleaner assigned to two properties.
- Backup cleaner availability.
- Planner rerun idempotency.
- Reclean and maintenance follow-up.

## 7. ERPNext accounting contract

RC8 distribution fields are operational snapshots only.

```text
OTA room-rate total
→ Hotel Reservation price snapshot
→ existing folio charge workflow
→ ERPNext Sales Invoice and tax template
```

There is no direct route:

```text
Distribution Event → GL Entry
Distribution Event → Payment Entry
Distribution Event → Stock Entry
```

Foreign currency remains Needs Review until Finance approves a conversion/repricing policy. Do not manually change the currency label while leaving the amount unchanged, a remarkably efficient way to create fictional revenue.

## 8. Required UAT

1. Import valid iCal with all-day dates.
2. Confirm checkout date remains sellable.
3. Confirm CLOSED/Blocked events do not become guest names.
4. Confirm exact echoes do not create phantom conflicts.
5. Confirm partial overlaps remain visible.
6. Verify private/loopback/redirect iCal URLs are rejected.
7. Verify public feed token rotation invalidates the prior URL.
8. Send a signed Generic JSON booking.
9. Retry the same external reference and verify one reservation.
10. Submit unmapped-room, no-availability, invalid price basis, and foreign-currency cases; each must enter Needs Review.
11. Test modification and cancellation review paths.
12. Test controlled check-in against clean, dirty, and blocked rooms.
13. Submit a one-time pre-arrival form twice; the second submission must fail.
14. Run turnover planner twice; no duplicate housekeeping task may appear.
15. Reconcile reservation charges, Sales Invoice, taxes, Payment Entry, GL, and Stock Ledger through the existing Production Gate.

## 9. Rollback

If RC8 migration or smoke fails:

1. Stop traffic.
2. Restore the pre-upgrade database and files backup on the isolated rehearsal bench.
3. Restore the previous application source/image.
4. Run migrate/build/cache clear/restart.
5. Verify version and source fingerprint.
6. Record immutable rollback evidence.

Do not delete distribution events or reservations to make reconciliation green. Preserve evidence and fix the source or mapping.
