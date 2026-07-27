# Hotel PMS v0.7.0 — Guest-facing and Privacy

## Public routes

- `/hotel-book?property=<public-slug>`: direct booking engine.
- `/hotel-guest#token=<raw-token>`: secure reservation portal.
- `/hotel-checkin#token=<raw-token>`: self check-in form.

Raw tokens are shown only when created and are stored only as SHA-256 hashes. New links use URL fragments, copy the token into browser `sessionStorage`, remove it from the address bar, and send token-bearing API calls through POST bodies.

## Setup order

1. Keep **Enable Public Booking Engine** disabled.
2. Configure the property public slug, SEO title/description, profile, contact details, public gallery, policy, terms, privacy notice, and Payment Gateway Account. Public images must use `/files/` rather than `/private/files/`.
3. Enable public display on each Hotel Room Type and choose its Public Rate Plan.
4. Configure Customer Group, Territory, Booking Deposit Item, server-controlled deposit percentage, outgoing email, Payment Gateway, and tax settings.
5. Configure Frappe site-level HTTP rate limiting in addition to the endpoint-specific guest throttles.
6. Test availability against ordinary reservations and group room blocks, retry/idempotency, simultaneous booking, self check-in, cancellation fees, Payment Requests, privacy requests, and manager overrides in staging.
7. Enable public booking only after UAT, security review, backup, and restore rehearsal.

## Inventory and money rules

The booking engine uses the same room and room-type capacity functions as Front Office. Active group room blocks are subtracted before advertising availability, and the Reservation controller revalidates inventory under database locks before saving.

The required deposit percentage is configured only in **Hotel PMS Settings → Public Booking Deposit Percent**. The public API never accepts a guest-supplied deposit percentage. Payment Requests, Sales Orders, Sales Invoices, Payment Entries, and receivables remain ERPNext documents.

## Guest identity model

ERPNext `Customer` and `Contact` remain the master records. `Hotel Guest Profile` extends them with preferences, consent, privacy status, risk status, aggregate stay statistics, and hotel-specific service notes. Returning guests are resolved by normalized email or phone. Merge operations use ERPNext document merge rather than copying financial records.

## Privacy model

The module provides:

- consent records;
- configurable retention dates;
- data-access request and JSON export;
- correction request;
- marketing opt-out;
- anonymization after cooling period and approval;
- blocks against anonymization while active reservations, receivables, or retention holds exist;
- controlled warning, review, online-block, and full-block records.

Anonymization removes Contact email/phone details and guest-profile preferences while retaining accounting and operational documents required for legitimate records. Customer naming rules differ by site, so Customer-ID rename behavior must be rehearsed on staging.

## Deliberate limitations

- ID image upload is not exposed on the public self check-in page. Front Office can verify or upload it under the global photo policy.
- Payment-gateway callback behavior must be tested with the chosen provider.
- The public page includes endpoint throttling and a honeypot, but production should add reverse-proxy/WAF protections appropriate to the threat level.
- Guest merge and anonymization require manager review, backup, and staging rehearsal.
- OTA/channel-manager synchronization is not part of v0.7.0.
