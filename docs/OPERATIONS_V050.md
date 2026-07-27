# Hotel PMS v0.5.0 — Housekeeping & Engineering Mobile

## Scope

This release implements one operational chain across Front Office, Housekeeping, and Engineering:

```text
Guest checkout / complaint
        ↓
Housekeeping task or maintenance ticket
        ↓
Assignment → timer → checklist → repair when required
        ↓
Supervisor inspection
        ↓
Room ready notification and room-status history
        ↓
Recurring-problem analysis and SOP Candidate
```

ERPNext remains the source of truth for users, suppliers, assets, purchasing, stock, accounting, and payments. The v0.5 operational documents do not create a second supplier, asset, customer, or financial ledger.

## New routes

- Front desk: `/app/hotel-front-desk`
- Mobile operations: `/app/hotel-housekeeping-mobile`
- Housekeeping performance: `/app/query-report/Hotel%20Housekeeping%20Performance`
- Housekeeping activity: `/app/query-report/Hotel%20Housekeeping%20Activity`
- Maintenance SLA: `/app/query-report/Hotel%20Maintenance%20SLA`
- Room history: `/app/query-report/Hotel%20Room%20History`

The mobile route is a responsive Frappe Desk page. Realtime events refresh open pages immediately. Notification Log entries preserve an in-app alert when the receiving user is not staring at the page, a rare but documented human behavior.

## Roles

Assign only the roles required for each person:

- `Housekeeping`: execute assigned cleaning, checklist, Lost & Found, and damage reports.
- `Housekeeping Supervisor`: assignment, inspection, reclean decision, reports, and Lost & Found custody.
- `Engineering`: acknowledge, start, pause, and complete repairs.
- `Engineering Supervisor`: assignment, SLA oversight, closure, and SOP review.
- `Front Desk`: room-ready visibility, guest-waiting priority, complaints, and room history.
- `Hotel Manager`: cross-department oversight and approval.

Supervisors do not need ERPNext accounting roles unless they also perform accounting work.

## Hotel PMS Settings

Open `Hotel PMS Settings` and review:

1. **Enable Realtime Operations Notifications**: default ON.
2. **Require Cleaning Checklist Before Completion**: default OFF. Enable after every active property/task type has a template.
3. **Require Supervisor Inspection Before Room Ready**: default ON.
4. **Lost & Found Retention Days**: default 90.
5. **Auto-create SOP Candidate**: default OFF until problem codes are used consistently.
6. **Repeated Problem Threshold**: default 3.
7. Engineering response and resolution SLA minutes by priority.
8. **Enable Photo Uploads**: remains default OFF for storage-limited VPS installations.

When photo uploads are OFF, parent and child evidence fields are hidden where practical and image uploads are blocked server-side. Existing images are not deleted.

## Checklist configuration

Create `Hotel Cleaning Checklist Template` documents.

Recommended minimum templates:

- Checkout Clean, property fallback.
- Stayover Clean, property fallback.
- Post-Maintenance Cleaning, property fallback.
- Room-type-specific templates only where room construction or amenities differ materially.

Only one enabled template is allowed for the same property, room type, and task type. This avoids two templates both insisting they are the standard, a conflict normally reserved for meetings.

Each item supports:

- Area and sequence.
- Critical flag.
- Scoring weight.
- Optional photo requirement.
- Practical instructions.

Use `examples/cleaning_checklist_items.csv` as the implementation baseline.

## Checkout and cleaning workflow

1. Front Office completes controlled checkout.
2. The reservation changes the room to `Available / Dirty` and creates one idempotent `Checkout Clean` task.
3. Housekeeping roles receive a realtime and Notification Log alert.
4. The task calculates priority from task type, next arrival, and guest-waiting flag.
5. Supervisor assigns a housekeeper, or a housekeeper starts and self-assigns an open task.
6. Starting changes the room to `Cleaning` and starts the timer.
7. Pause time is excluded from net cleaning time.
8. Every checklist item must be resolved before completion when checklist enforcement is enabled.
9. Completion changes the room to `Ready for Inspection` when supervisor inspection is required.
10. A pass changes the room to `Inspected` and notifies Front Office.
11. A failed inspection changes the task and room to `Reclean Required`; inspection wait and reclean wait are excluded from net working time.

## Priority queue

Higher score appears first:

- Guest already waiting.
- Arrival within 60 minutes.
- VIP flag when later connected to guest-profile workflow.
- Checkout cleaning.
- Post-maintenance cleaning.
- Stayover and routine work.
- Deep cleaning without an imminent arrival.

Front Office or supervisors can set or clear `Guest Waiting` from the mobile page.

## Lost & Found

A housekeeper can report an item directly from a cleaning task. The record stores:

- Room, reservation, task, finder, time, and exact location.
- Category, description, high-value/sensitive flag, seal number, and storage location.
- Optional photo subject to the global photo policy.
- Chain-of-custody events.
- Guest contact, return/shipping, and disposal information.

Sensitive items cannot be disposed through an ordinary status change. Management handling is required.

## Engineering request and SLA

FO or Housekeeping creates one `Hotel Maintenance Ticket` with an idempotency key. The ticket stores:

- Source, room/reservation, guest impact, safety risk, and room-sale block.
- Problem category and consistent problem code.
- ERPNext Asset, Supplier, and Purchase Order links.
- Response and resolution deadlines.
- Work log, root cause, corrective action, parts/materials, prevention/HIKMAH, and cleaning instructions.

Priority can be elevated automatically when the ticket has a safety risk or the guest cannot use the facility.

The 15-minute scheduler updates SLA status and sends one breach alert per response/resolution breach.

## Housekeeping-to-Engineering handoff

When a checklist item is set to `Reported to Engineering`, defect notes are required and the system automatically creates one deterministic Engineering ticket. Then:

1. The checklist row links to the maintenance ticket.
2. The housekeeping task pauses as `Waiting Engineering`.
3. Waiting time is excluded from cleaning time.
4. The room can be blocked from sale when required.
5. After repair, the linked checklist item resets to `Pending` so Housekeeping must verify it.
6. The existing cleaning task resumes instead of creating a duplicate task.

If a ticket originated outside Housekeeping and post-repair cleaning is required, the system creates one idempotent `Post-Maintenance Cleaning` task.

## Repair completion and room release

Engineering must provide root cause and corrective action. When post-maintenance cleaning is required, practical cleaning instructions are mandatory.

The room is not returned as ready until:

- Engineering marks repair complete.
- Housekeeping completes the linked or generated cleaning task.
- Supervisor inspection passes when required.

Only then does the system restore the operational status, set housekeeping to `Inspected`, resolve the maintenance ticket, and notify FO and Engineering.

## Room history

`Hotel Room Status Log` is the single timeline for controlled room-state changes. The Room History report combines:

- Status transitions.
- Housekeeping tasks and timing.
- Maintenance tickets, cause, action, and prevention.
- Lost & Found.

Every controlled status helper uses a unique event key where retry is possible.

## KPI reports

### Hotel Housekeeping Activity

Detailed list by date, room, housekeeper, type, status, assigned/start/complete/inspection times, net cleaning minutes, pause minutes, turnaround, and first-pass result.

### Hotel Housekeeping Performance

Summary by housekeeper:

- Completed rooms by type.
- Average net cleaning time.
- Average checkout-to-ready time.
- First-pass inspection percentage.
- Reclean percentage.
- On-time percentage.

Speed is not the only score. Otherwise the optimal strategy would be to declare a room clean before entering it, an innovation management has declined.

### Hotel Maintenance SLA

Shows priority, response/resolution timing, room blocks, assignee, and SLA breaches.

## SOP Candidate

A completed maintenance ticket can create one `Hotel SOP Candidate`. It copies:

- Symptoms and root cause.
- Repair steps.
- Post-repair cleaning steps.
- Materials/tools.
- Warnings.
- Prevention/HIKMAH.
- Evidence subject to photo policy.
- Repeat occurrence count.

Workflow statuses support Engineering review, Housekeeping review, management approval, and publication. Both reviewers and a published SOP reference are required before publication.

Auto-generation is available but disabled by default. It requires consistent problem codes and sufficient prevention/cleaning information.

## Duplicate-entry controls

- Checkout housekeeping task: deterministic unique key.
- Post-maintenance task: deterministic unique key.
- Maintenance request: caller key plus room/location.
- Lost & Found report: caller key plus task.
- Lost & Found custody event: caller key plus record.
- Inspection: unique caller key.
- SOP Candidate: one unique source maintenance ticket.
- Room status logs: deterministic keys for retryable transitions.
- Action endpoints are state-idempotent when a repeated click reaches an already-completed state.

No v0.5 scheduler creates Sales Invoice, Payment Entry, Purchase Order, or accounting journals.

## Upgrade from v0.4.0

```bash
cd ~/frappe-bench
bench --site erp.example.com backup
# replace app source with v0.5.0
bench --site erp.example.com migrate
bench build --app hotel_pms
bench --site erp.example.com clear-cache
bench restart
```

After migration:

1. Assign supervisor roles.
2. Configure SLA minutes.
3. Import or create checklist templates.
4. Keep checklist enforcement OFF during initial setup.
5. Test the mobile route on actual staff phones.
6. Complete UAT below.
7. Enable checklist enforcement only after template coverage is confirmed.
8. Keep automatic SOP Candidate creation OFF until problem-code discipline is verified.

## Minimum UAT

1. Checkout creates exactly one cleaning task on repeated clicks/retry.
2. Checkout alert reaches Housekeeping roles.
3. Supervisor assigns a valid Housekeeping user; invalid role is rejected.
4. Start changes room to Cleaning.
5. Pause and resume exclude waiting time.
6. Guest-waiting flag raises queue priority.
7. Checklist cannot complete with Pending items when enforcement is ON.
8. Critical checklist failure cannot pass supervisor inspection.
9. Reclean returns to the same task and records a second inspection attempt.
10. Inspection pass notifies FO and changes room to Inspected.
11. Lost & Found retry creates one record.
12. Custody events preserve chronological handover history.
13. Photo OFF hides/rejects new evidence images, including child rows.
14. FO complaint creates one Engineering ticket.
15. Safety risk elevates priority.
16. Room block writes Out of Service/Waiting Engineering history.
17. SLA response breach notifies once.
18. Housekeeping defect pauses the original timer.
19. Repair completion resets the failed checklist row to Pending.
20. Existing housekeeping task resumes instead of duplicating.
21. External maintenance ticket creates one post-maintenance task when required.
22. Room remains unavailable before post-cleaning inspection.
23. Passing post-cleaning resolves ticket and returns room.
24. Maintenance without cleaning restores the correct Occupied/Available state.
25. Repeat problem count increments by problem code.
26. SOP Candidate cannot publish without both reviewers and reference.
27. Room History displays linked FO/HK/Engineering events.
28. Performance report excludes pause time.
29. Housekeeping users cannot inspect their own room unless they also hold supervisor authority.
30. No accounting or stock document is created by operations schedulers.

## Known limitations

- Realtime notification requires an active Frappe session; browser system notification permission is optional.
- This is a responsive Desk page, not an offline-capable native mobile application.
- Photos are not compressed automatically in v0.5.0; keep uploads disabled or enforce site file-size limits on small VPS installations.
- Housekeeping shift rosters, linen par stock, minibar issue, laundry, and payroll incentive calculation remain outside this release.
- Full bench integration, concurrency, permission, migration, and browser tests still require a staging ERPNext v16 site.
