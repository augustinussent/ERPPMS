# Changelog

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
