# Hotel PMS ERPNext v1.0.0-rc6
## Intelligence & Control Manual

### 1. Upgrade

```bash
cd ~/frappe-bench
bench --site hotel-staging.example.com backup --with-files
# replace the hotel_pms source with RC6
bench --site hotel-staging.example.com migrate
bench build --app hotel_pms
bench --site hotel-staging.example.com clear-cache
bench restart
```

Perform the upgrade on staging first. RC6 creates new operational DocTypes and adds Production Gate checks. It does not migrate or duplicate accounting balances.

### 2. Assign roles

Use existing Frappe roles and property assignments:

- System Manager: platform configuration and approval.
- Hotel Manager: intelligence review and payment correction approval.
- Night Auditor: scan and finding review.
- Hotel Intelligence Analyst: read/review intelligence evidence.
- Accounts User: request a Payment Correction.
- Accounts Manager: approve and execute governed corrections.

Every non-System Manager user still requires `Hotel User Property Access`.

### 3. Configure intelligence

Create one `Hotel Intelligence Config` per property and agent type.

Recommended initial configuration:

```text
Agent Type: Night Audit Anomaly
Enabled: OFF during first staging review
Mode: Suggest
Confidence Threshold: 85
Autopilot Approved: OFF
Configuration JSON:
{
  "cash_variance_threshold": 1000,
  "stock_posting_grace_minutes": 20
}
```

Do not enable Autopilot before a dedicated Production Gate review. RC6 contains no financial or stock autopilot executor.

### 4. Run Night Audit scan

Open:

```text
/app/hotel-intelligence-console
```

Select Property and Business Date, then choose **Run Night Audit Scan**.

Review Critical findings first. Acknowledge means the issue is assigned and understood. Resolve requires resolution notes. Mark False Positive only after verifying the source documents.

Never clear a finding by manually editing or deleting ERPNext vouchers. Correct the source workflow and rerun the scan.

### 5. Correct a payment

Open the relevant ERPNext Payment Entry and select:

```text
Hotel PMS → Correct Payment
```

The matrix presents only legal actions.

#### Delete Draft

Used only when the Payment Entry remains Draft. Approval is mandatory. Deleting the draft has no GL effect.

#### Create Refund

Available only for a submitted hotel deposit with remaining refundable balance. Approval is mandatory. Execution calls the existing hotel refund function and creates one idempotent draft ERPNext Payment Entry of type Pay.

Finance must review and submit that draft through normal ERPNext controls.

#### Manual Review

The system refuses automatic execution. Finance determines the proper ERPNext correction, preserving the audit trail.

### 6. Integration registry

Seed or refresh the registry from the Intelligence Console using **Seed Integration Registry**.

Create `Hotel Integration Connection` for a property. Use **Test Connection**. Complete every mandatory go-live check before changing status to Live.

A Planned or Recipe item cannot be marked Live merely because someone obtained an API key and feels optimistic.

### 7. Production Gate

Open `/app/hotel-production-gate` and run automated checks. RC6 blocks Go when:

- Autopilot is configured without approval.
- Critical intelligence findings remain open or acknowledged.
- Payment Corrections are Failed or Approved but not executed.
- A Live integration is not Shipped/Adapter or has incomplete mandatory checks.

### 8. RC6 bench smoke

On the prepared disposable Frappe v16 integration site:

```bash
export BENCH_PATH="$HOME/frappe-bench"
export SITE="hotel-test.localhost"
export RC6_TEST_PROPERTY="TEST-HOTEL"
export GATE_RUN="HPG-2026-00001"   # optional

apps/hotel_pms/ci/run_rc6_bench_smoke.sh
```

The test fails if intelligence seeding/scanning changes financial or stock document counts.

### 9. Required staging UAT

Verify:

1. Property isolation for all new DocTypes.
2. Idempotent repeated Night Audit scans.
3. Finding auto-resolution and False Positive preservation.
4. Payment correction approval separation.
5. Refund amount cannot exceed ERPNext-derived net deposit.
6. Repeat execution returns the previous result.
7. Refund result remains Draft until Finance submits it.
8. Integration status Live is blocked by missing checks.
9. Production Gate receives the RC6 checks.
10. Submitted ERPNext ledger counts remain unchanged by advisory scans.
