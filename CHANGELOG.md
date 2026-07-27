# Changelog

## 1.0.0-rc4 - Production Validation Pack

- Added frozen release manifests with normalized source fingerprints, pinned Frappe/ERPNext versions, image digest, artifact checksum, and controlled promotion target.
- Added immutable blank-install, upgrade, restore, rollback, concurrency, performance, and security rehearsal records.
- Added parallel-run reconciliation batches with CSV import, tolerances, mandatory metric coverage, and immutable row evidence.
- Added immutable validation evidence records linked to Production Gate checks.
- Extended the Production Gate with manifest integrity, exact-artifact rehearsal checks, parallel-run reconciliation, and controlled release promotion.
- Added standalone RC promotion and parallel-run validation tools without creating any ERPNext financial or stock document.
- Kept the release as an RC because bench, restore, concurrency, performance, security, and departmental evidence must still be executed in the target environment.

## 1.0.0-rc3 - F&B Operational Depth

- Added KDS v2 with accept/start, progress, course, allergy, late aging, recall, sound, and realtime updates.
- Added ERPNext Item recipes and one idempotent Material Issue Stock Entry per KOT.
- Added mutually exclusive outlet inventory policies to prevent invoice and recipe stock posting from running together.
- Added Hotel ERP Sync Log revision-key retry for cancelled Stock Entries.
- Added menu/recipe CSV preview and commit workflow.
- Added Restaurant Stock Reconciliation report and recipe-aware Production Gate checks.
- Corrected the prior localization/communication candidate label to 1.0.0-rc2.

## 1.0.0-rc2 - Localization and Communication Adoption

- Added governed localization packs with Indonesia labels/locale and strict ERPNext tax-template validation.
- Added Meta Cloud API WhatsApp connections, idempotent message ledger, async delivery, status webhook, and inbound message inbox.
- Added private re-encoded guest ID/address documents with Verify-and-Discard purge.
- Added one-tax-profile-per-invoice enforcement and automatic group invoice separation by customer plus tax profile.
- Added CI guard proving localization/communications do not create ERPNext financial or stock documents.

## 1.0.0-rc1
- Production gate evidence model, reconciliation checks, departmental sign-off, cutover and rollback tooling.
- Concurrency, performance, security, restore-drill, and pinned-container scaffolding.
- This is a release candidate and requires environment-specific gate approval.


## 0.9.0

- Multi-property access control and property switcher.
- Resumable onboarding and configuration export.
- CSV migration dry run, commit, audit, and safe rollback.
- Versioned API v1, OpenAPI, Postman, idempotency, and channel adapter boundary.
- HMAC webhook queue with retry and dead-letter replay.
- Health snapshots, disk/backup/sync monitoring, and backup checksum verification.
- CI, bench-test and Playwright scaffolding, plus security runbook.

## 0.8.0 - 2026-07-21

- Added restaurant outlets, dining areas, physical tables, table reservations, table-state management, outlet menu items, and a responsive Restaurant POS console.
- Added duplicate-safe restaurant orders for dine-in, room service, takeaway, delivery, and public QR ordering.
- Added captain confirmation for QR orders, daily KOT numbering per outlet, kitchen-station routing, thermal KOT print format, Kitchen Display System, and per-item preparation states.
- Added controlled bill request, exact quantity-conserving item splits, equal direct-payment splits, and deterministic split invoice creation.
- Added draft ERPNext POS Invoice creation for cash/card/UPI and draft Sales Invoice creation for room or city-ledger posting.
- Added invoice submit/cancel synchronization so restaurant orders cannot be completed without submitted ERPNext documents and cancelled invoices reopen the billing workflow.
- Added manager-governed complimentary orders that do not create revenue documents.
- Added public table QR menus with token-scoped access, request throttling, idempotency keys, captain confirmation, active-table locking, and public-image controls.
- Added guest laundry rate cards, guest/self-service requests, pickup/count/process/ready/return workflow, promised-ready tracking, overdue monitoring, printable dockets, and duplicate-safe folio posting.
- Added guest experiences with capacity checks, guest-portal booking, staff confirmation, and duplicate-safe folio posting.
- Added cross-department shift handover with submission, acknowledgment, close, and carry-forward of open items.
- Added Restaurant Sales and Laundry Performance reports plus restaurant, kitchen, laundry, and handover operational pages.
- Extended the global photo policy to restaurant menu and guest-experience images.
- Added service-operation roles, ERPNext POS/Sales Invoice linkage fields, setup fixtures, examples, pure-rule tests, and v0.8 implementation documentation.

## 0.7.0 - 2026-07-21

- Added a public direct-booking page with property profile, gallery, room-type presentation, live deterministic rates, restrictions, vouchers, and real inventory shared with Front Office and group room blocks.
- Added duplicate-safe public multi-room booking with database-backed reservation idempotency and server-controlled deposit requirements.
- Added secure guest portal and self check-in routes using random tokens stored only as SHA-256 hashes, with expiry, usage limits, purpose scope, rate limiting, and append-only action logs.
- Moved guest tokens from query strings to URL fragments and POST bodies to reduce exposure in browser history, referrers, and access logs.
- Added guest booking confirmation, cancellation confirmation, invoice/outstanding view, payment-request creation, self check-in, and privacy-request controls.
- Added Hotel Guest Profile 360 with stay statistics, preferences, complaint/Lost & Found context, consent history, and controlled blacklist status.
- Added returning-guest resolution through ERPNext Customer and Contact instead of creating a duplicate guest master.
- Added duplicate-candidate detection and manager-controlled ERPNext Customer merge workflow.
- Added consent records, retention dates, data-access exports, correction requests, marketing opt-out, and governed anonymization that blocks active stays, receivables, and retention holds.
- Added controlled warning, review, online block, and full block rules with manager override audit fields.
- Added public-profile SEO fields, slug validation, public-file image validation, HTML escaping, and a booking-form honeypot.
- Added booking confirmation Print Format and manager tools for issuing one-time-visible guest portal links.
- Added daily guest-token and blacklist expiry jobs.

## 0.6.0 - 2026-07-21

- Added deterministic stay quoting with rate seasons, date-level rate calendar overrides, derived rate plans, floors, and stay/arrival/departure restrictions.
- Added governed below-floor rate approvals with expiry and audit fields.
- Added voucher rules, reservation-safe redemption records, usage limits, customer scope, and idempotent release on cancellation.
- Added travel-agent contracts, gross/net pricing basis, reservation commission accrual, settlement batches, and duplicate-safe ERPNext Purchase Invoice drafts.
- Added configurable Hotel Tax Profile with service charge, tax basis, inclusive/exclusive pricing, rounding, and ERPNext Sales Taxes Template mapping.
- Added per-line folio tax display for individual, group, and city-ledger charges while ERPNext remains the accounting source of truth.
- Added controlled folio split/transfer/reversal across guest, group, and city-ledger folios with exact amount conservation and immutable audit records.
- Added unified checkout page for charges, invoices, deposits, direct-bill approval, payment requests, transfers, and final checkout.
- Added city-ledger accounts, credit limits, direct-bill approvals, folios, invoices, and outstanding reporting.
- Added cashier shifts, drawer movements, ERPNext Payment Entry/POS reconciliation, variance reasons, and manager review above a configurable threshold.
- Added ERPNext Payment Request creation for submitted Sales Invoices with deterministic sync keys and duplicate prevention.
- Added revenue calendar, checkout, and cashier operational pages plus Rate Overview, Cashier Reconciliation, and City Ledger Outstanding reports.
- Extended ERPNext synchronization fields to Payment Request, Purchase Invoice, Sales Invoice, Payment Entry, and POS Invoice.
- Added daily approval expiry and travel-agent settlement status reconciliation.

## 0.5.0 - 2026-07-20

- Added responsive Housekeeping and Engineering mobile operations page.
- Added realtime checkout, assignment, inspection, room-ready, Engineering, Lost & Found, and SLA notifications.
- Added prioritized cleaning queue with guest-waiting and next-arrival scoring.
- Added start, pause, resume, completion, inspection-wait, and reclean timing with excluded waiting time.
- Added versioned cleaning checklist templates and task checklist rows by property, room type, and task type.
- Added supervisor inspection scoring, critical-item guards, first-pass tracking, and reclean workflow.
- Added Lost & Found with sensitive-item handling and chain of custody.
- Expanded Maintenance Ticket into a unified FO/HK/Engineering service request with guest impact, safety risk, room block, response/resolution SLA, work log, recurring-problem detection, and post-maintenance cleaning.
- Reused an originating housekeeping task after repair to avoid duplicate work orders; checklist defects reset to Pending for verification.
- Added controlled room-status timeline and consolidated Room History report.
- Added Housekeeping Activity, Housekeeping Performance, and Maintenance SLA reports.
- Added SOP Candidate with Engineering/Housekeeping review and controlled publication.
- Extended global photo policy to checklist, inspection, Lost & Found custody, and SOP evidence fields.
- Added operation-level idempotency keys and state-idempotent action endpoints.
- Made `Reported to Engineering` checklist results create and link one deterministic Engineering ticket automatically.
- Added duplicate-safe Lost & Found custody events.
- Added pure-rule tests for cleaning priority, inspection scoring, timer exclusion, SLA status, and SOP threshold.

## 0.4.0 - 2026-07-20

- Added a dedicated Hotel Front Desk page with arrivals, departures, in-house stays, no-show review, and room-state summaries.
- Added a 14-day physical-room tape chart.
- Added idempotent quick multi-room booking with aggregate room-type capacity validation.
- Added controlled room move, extend-stay, and early-departure actions with immutable change logs.
- Added cancellation and no-show policies, fee calculation, waiver governance, folio fee posting, and printable confirmation.
- Added Guest Registration Card, registered occupants, identity-retention controls, and optional verification before check-in.
- Added duplicate-safe draft ERPNext Payment Entries for deposits and refunds.
- Added Payment Entry synchronization keys and reservation links; submitted entries update reservation deposit totals.
- Added check-in guards for room operational and housekeeping readiness.
- Blocked direct reservation status and standard document cancellation paths that could bypass commercial policy.
- Expanded room and property permissions for operational roles.
- Added pure-rule tests for room nights, stay totals, and cancellation calculations.

## 0.3.0 - 2026-07-20

- Added a global administrator toggle for Hotel PMS photo uploads, disabled by default.
- Hidden photo fields while disabled and blocked image uploads through UI, standard upload endpoint, direct File creation, and DocType validation.
- Added deterministic ERPNext synchronization keys and the `Hotel ERP Sync Log` audit ledger.
- Added hidden unique sync keys to Project, Quotation, Sales Order, and Sales Invoice.
- Added per-charge Sales Invoice tracking for individual folios.
- Added database uniqueness for folios and operational idempotency keys.
- Added duplicate-safe group quotation, sales order, project, sales invoice, participant reservation, folio, housekeeping, and preventive-maintenance creation.
- Added daily conservative link reconciliation and administrator sync-health actions.
- Checkout now creates its housekeeping task immediately without duplicate scheduler entries.

## 0.2.0 - 2026-07-19

- Added Group Booking lifecycle, tentative expiry, and room-block cut-off release.
- Added rooming list and participant reservation generation.
- Added meeting/function-space capacity and conflict validation.
- Added package templates, component allocation, rate selection, and dated package postings.
- Added ERPNext Quotation, Sales Order, Project, Group Folio, split-customer Sales Invoice, and cost links.
- Added BEO revision control and Hotel Group Profitability report.
- Added Hotel Group Confirmation Letter print/PDF facility.
- Extended night audit to post due group-package components.
- Fixed the Hotel PMS Settings controller class name for Frappe controller loading.
