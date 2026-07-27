# Roadmap setelah Hotel PMS v0.9.0

## v1.0.0 — Production Gate

### 1. Real bench validation

- Pin Frappe dan ERPNext v16 release.
- Build custom container image.
- Install dan migrate dari blank site serta upgrade v0.8 → v0.9.
- Run complete bench test suite.
- Run MariaDB concurrency tests.
- Run worker, scheduler, Redis, websocket, and reverse-proxy tests.

### 2. Accounting acceptance

- Reservation-to-invoice reconciliation.
- Deposit/refund reconciliation.
- POS and stock reconciliation.
- Travel-agent Purchase Invoice reconciliation.
- City-ledger aging.
- Cashier shift reconciliation.
- Tax/service charge review by accountant.
- Zero unexplained material difference.

### 3. Inventory and operations acceptance

- Last-room concurrency.
- Last-table and experience-capacity concurrency.
- Housekeeping-to-ready timing.
- Engineering SLA and room block.
- KOT, invoice, stock, laundry, and room posting.

### 4. Security acceptance

- Property/tenant isolation penetration test.
- API and guest-token test.
- SSRF, CSRF, XSS, IDOR, upload, rate-limit, and session review.
- Dependency/container scan.
- Secret rotation drill.
- Access review sign-off.

### 5. Reliability and disaster recovery

- External health monitor.
- Log aggregation and alerts.
- Database and file backup schedule.
- Isolated restore drill.
- Disaster-recovery drill.
- Approved RPO and RTO.
- Rollback drill.

### 6. Performance

- Expected number of rooms, properties, outlets, users, reservations, folio rows, and KOT.
- Peak booking, check-in, checkout, and POS load.
- Slow-query review and required indexes.
- File-storage growth forecast.

### 7. Operational readiness

- Department UAT signed.
- Training completed.
- SOP and escalation approved.
- Parallel run completed.
- Support roster and incident severity defined.
- Go-live freeze and rollback decision points approved.

## Deferred roadmap after v1.0

- OTA/channel manager adapters.
- Revenue forecasting and automated recommendations.
- Offline POS queue and native printer bridge.
- Airport dispatch and vehicle schedule.
- Spa/resource calendar.
- Advanced guest loyalty.
- Mobile-native application packaging.
