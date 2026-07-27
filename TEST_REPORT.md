# Hotel PMS v0.5.0 Validation Report

Validation date: 2026-07-20

## Release scope validated

- Responsive Housekeeping and Engineering operations page
- Realtime and persistent operational notifications
- Checkout-to-cleaning task generation
- Priority queue and guest-waiting escalation
- Housekeeper assignment and work timer
- Cleaning checklist and automatic Engineering escalation
- Supervisor inspection and reclean loop
- Lost & Found with chain of custody
- Engineering ticket, SLA, room blocking, and post-maintenance cleaning
- Unified room-status timeline and operational reports
- Recurring-problem detection and SOP Candidate
- Global photo-storage policy across new evidence fields
- Operation-level duplicate-entry controls

## Automated static validation completed

- Python files compiled: 142
- JavaScript files parsed by Node: 17
- JSON files parsed: 53
- DocType definitions checked: 46
- Duplicate DocType field names: 0
- Invalid field-order entries: 0
- Missing child-table targets: 0
- Missing custom Link targets: 0
- Invalid custom sort fields: 0
- JavaScript references to missing `hotel_pms.operations` endpoints: 0
- Referenced Hotel PMS Settings fields missing from the Settings DocType: 0
- Direct Python writes to Hotel Room status outside the centralized room-status helper: 0

## Executable pure-rule tests

Eleven tests passed:

1. Room-night calculation
2. Multi-room stay total
3. Percentage cancellation fee
4. Free-cancellation behavior
5. First-night cancellation fee
6. Cleaning priority when a guest is waiting
7. Work-duration calculation excluding pause time
8. Critical inspection failure blocks a pass
9. Pending checklist item blocks a pass
10. SLA breach calculation
11. SOP Candidate repeat threshold

Command:

```bash
PYTHONPATH=. python -m unittest discover -s hotel_pms/tests -v
```

## Duplicate-entry and retry controls reviewed

- Checkout cleaning uses a deterministic unique task key.
- Post-maintenance cleaning uses a deterministic unique task key.
- Checklist `Reported to Engineering` creates one deterministic linked ticket.
- Manual Engineering intake requires a caller idempotency key.
- Lost & Found reports use deterministic request keys.
- Lost & Found custody events accept an idempotency key and store it on the custody row.
- Supervisor inspections use a unique idempotency key.
- SOP Candidate creation is unique per source maintenance ticket.
- Controlled room-status transitions are serialized by a row lock and logged with retry keys.
- Start, completion, inspection, acknowledgement, repair completion, and closure actions are state-idempotent.
- No v0.5 scheduler creates a Sales Invoice, Payment Entry, Purchase Order, stock transaction, or general-ledger entry.

## Important source review findings resolved

- A checklist defect no longer requires duplicate manual data entry into a separate Engineering dialog. Selecting `Reported to Engineering` with notes now creates and links one Engineering ticket automatically.
- Lost & Found custody handovers now have retry protection.
- Room History report date filters now apply consistently to housekeeping, maintenance, Lost & Found, and room-status events.
- Room status writes from controlled FO, Housekeeping, and Engineering workflows use the centralized helper and one status timeline.

## Not validated in this environment

The following require a real Frappe/ERPNext v16 staging site:

- DocType migration and v0.5 patch execution
- MariaDB index creation on an existing production-sized dataset
- Browser rendering on actual Android/iOS devices
- Socket.IO/realtime delivery through the selected reverse proxy
- Notification Log behavior for each deployed Frappe v16 patch release
- User Permission behavior in a multi-property installation
- Permission checks using real Housekeeping, Supervisor, Engineering, FO, and Manager accounts
- Parallel-request behavior against MariaDB row locks
- Scheduler execution and one-time SLA breach notification
- PDF/image attachment behavior with the global photo toggle ON and OFF
- End-to-end checkout, cleaning, inspection, repair, post-cleaning, and room-return workflow
- Full backup/restore and rollback rehearsal

## Required staging gate

Do not deploy v0.5.0 directly to production. Complete the 30 UAT scenarios in `docs/OPERATIONS_V050.md`, test on the actual staff phones and network, verify role permissions, and complete a backup/restore rehearsal first.
