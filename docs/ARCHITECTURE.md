# Architecture and Data Ownership

## ERPNext remains the source of truth for

- Company and chart of accounts
- Customers, contacts, addresses, and corporate accounts
- Items, taxes, price lists, and discounts
- Sales Invoice, POS Invoice, Payment Entry, Journal Entry, and receivables
- Warehouses, stock ledger, procurement, suppliers, and purchase orders
- Assets and asset maintenance history
- Employees/users and permissions

## Hotel PMS owns

- Property, room type, room, and operational room status
- Rate plan and room availability
- Reservation lifecycle
- Folio and operational charges
- Night audit
- Housekeeping task workflow
- Hotel maintenance ticket workflow and preventive schedules
- Group booking, room blocks, rooming list, event functions, BEO, package schedule, group folio, and confirmation letter

## Integration keys

| PMS document | ERPNext document | Relation |
|---|---|---|
| Hotel Reservation | Customer | Guest and billing party |
| Hotel Reservation | Contact | Guest contact details |
| Hotel Property | Company | Legal/accounting entity |
| Hotel Property | Cost Center | Property or department P&L |
| Hotel Room | Asset | Physical room/equipment grouping |
| Hotel Room | Warehouse | Minibar or room stock location |
| Hotel Room Type | Item | Room revenue service item |
| Hotel Folio Charge | Item | Revenue/stock/tax mapping |
| Hotel Folio | Sales Invoice | Checkout billing |
| Hotel Maintenance Ticket | Supplier | External vendor |
| Hotel Maintenance Ticket | Purchase Order | Approved outsourced work/material |
| Hotel Group Booking | Project | Event-level profitability dimension |
| Hotel Group Booking | Quotation / Sales Order | Commercial offer and contract |
| Hotel Group Folio Charge | Sales Invoice | Group, individual, or direct-bill settlement |
| Hotel Group Booking | Purchase Invoice | Direct event cost |

## Anti-duplication rules

1. Do not create a second guest master independent of ERPNext Customer.
2. Do not calculate accounting balances only inside the folio.
3. Do not copy POS revenue into a second Sales Invoice.
4. Every external integration must carry an idempotency key.
5. Never allow room availability updates without a transaction and conflict check.
