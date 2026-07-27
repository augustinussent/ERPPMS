# Photo Storage and ERPNext Synchronization

## Global photo switch

Open **Hotel PMS Settings** as `System Manager` or `Hotel Manager`.

- `Enable Photo Uploads = Off` is the default for storage-limited VPS installations.
- Photo fields on Housekeeping and Maintenance forms are hidden.
- The standard Frappe upload endpoint rejects image uploads attached to Hotel PMS documents before a `File` record is created.
- Direct/API writes to photo fields are rejected by the relevant DocType controller.
- Existing photos are preserved. Turning the switch off does not silently delete audit evidence.
- PDFs and non-image operational attachments remain available.

The same settings screen provides:

- **Check ERPNext Sync**: read-only health inspection.
- **Reconcile Existing Links**: repairs links to documents that already exist. It never creates an invoice, order, or accounting entry.

Frappe's site-wide `max_file_size` can still be used as an additional ceiling. The Hotel PMS switch is more restrictive because it controls whether hotel evidence photos are allowed at all.

## Data ownership

ERPNext is the source of truth for:

- Customer, Contact, Address, Supplier, Item and Price List
- Company, Cost Center, Warehouse and Asset
- Quotation, Sales Order, Sales Invoice, POS Invoice, Payment Entry and accounting ledgers
- Purchase Order, Purchase Invoice and stock documents

Hotel PMS is the source of truth for:

- Reservation, room allocation and operational room status
- Individual and group folios before accounting transfer
- Group booking, room block, package schedule, BEO and meeting functions
- Housekeeping and hotel maintenance operations

PMS documents store ERPNext **Link** values. The application does not maintain a second Customer, Item, Supplier, Asset, or account master.

## Duplicate protection layers

### 1. Deterministic idempotency keys

Each operation that creates an ERPNext document receives a stable key, for example:

```text
QTN:GROUP:<group-booking>
SO:GROUP:<group-booking>
PROJECT:GROUP:<group-booking>
SI:FOLIO:<folio-and-charge-batch>
SI:GROUP-FOLIO:<folio-customer-charge-batch>
```

Repeating the command returns the existing active target. If the target was cancelled, a numbered retry key is used.

### 2. ERPNext unique sync field

ERPNext `Project`, `Quotation`, `Sales Order`, and `Sales Invoice` receive the hidden unique custom field:

```text
custom_hotel_sync_key
```

This is a database-level backstop against concurrent duplicate creation.

### 3. Hotel ERP Sync Log

`Hotel ERP Sync Log` records:

- operation and deterministic key
- PMS source document
- ERPNext target document
- payload hash
- status and completion timestamp

The log is inserted in the same database transaction as its target. A second concurrent request cannot claim the same key.

### 4. Per-charge invoice links

Each folio charge records its Sales Invoice. A cancelled or deleted draft invoice releases only its own charge rows. New charges can be invoiced later without reusing old charges.

### 5. Unique operational records

Database uniqueness is enforced for:

- one `Hotel Folio` per reservation
- one `Hotel Group Folio` per group booking
- folio and package idempotency keys
- automated housekeeping and preventive-maintenance task keys
- participant reservations generated from a group room/date combination

### 6. Conservative reconciliation

A daily reconciliation job repairs broken header/child links and PMS-to-ERPNext references. It does not create new accounting documents. Financial document creation remains an explicit user action.

## Remaining operational rule

Users must not manually create a second ERPNext transaction for a PMS event and then also press the PMS creation button. The sync key protects application-generated transactions, but no software can reliably identify every manually entered invoice whose description merely happens to resemble another invoice. Human creativity remains undefeated, merely constrained.
