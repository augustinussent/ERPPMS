# Hotel PMS v0.9.0 Platform Hardening

## Property isolation
Assign every operational user through **Hotel User Property Access**. System Manager and Administrator remain unrestricted. Hotel Manager can receive consolidated permission explicitly. Query and document permission hooks restrict all property-bearing PMS documents, including related restaurant and cashier documents.

## Onboarding
Use `/app/hotel-onboarding`. Create a resumable session, run readiness scan, build a plan, inspect the plan, then apply. The process reuses natural keys and does not duplicate Cost Centers, Warehouses, Hotel Property, rooms, rate plans, or outlets.

## Migration
Create **Hotel Migration Batch**, attach UTF-8 CSV, select preset/entity, and run `/app/hotel-migration-importer`. Dry run records every Insert, Update, Skip, Reject, or Review row. Deposit rows are always Review-only. Safe rollback is limited to draft/non-accounting documents.

## API
The supported surface is `/api/method/hotel_pms.api.v1.*`. Use normal Frappe token authentication, assigned property scope, and `X-Idempotency-Key` for writes. See `docs/openapi-v1.json` and the Postman collection.

## Webhooks
Webhook payloads are signed as `HMAC-SHA256(timestamp + '.' + body)`. Deliveries carry an idempotency key, retry exponentially, and enter Dead Letter after the configured maximum. Replay is explicit and audited.

## Health and backups
`/app/hotel-platform-console` displays disk, backup freshness, failed sync, and dead webhook conditions. Backup verification calculates a checksum and verifies readability; it does not replace an isolated restore drill.

## Production controls
Configure reverse-proxy TLS, HSTS, CSP, request-size limits, rate limits, and secret rotation. CI includes static validation and a bench-runner script, but the organisation must pin and operate a real Frappe v16 integration runner.
