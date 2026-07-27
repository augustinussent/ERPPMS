# Hotel PMS ERPNext v1.0.0-rc6 Release Notes

## Scope

RC6 implements Intelligence & Control patterns while retaining ERPNext as the single source of truth for accounting and inventory.

## Added

- Hotel Intelligence Config.
- Hotel Intelligence Run.
- Hotel Intelligence Decision.
- Hotel Night Audit Finding.
- Hotel Payment Correction.
- Hotel Integration Definition.
- Hotel Integration Connection.
- Hotel Integration Go Live Check.
- Intelligence Console and Night Audit Findings report.
- Payment Entry `Correct Payment` action.
- Governed explanation number grounding.
- Integration maturity registry.
- RC6 bench smoke and financial-document count guard.
- Production Gate intelligence, payment-correction, and integration checks.

## Night Audit findings

The scanner detects missing folios, stale stays, open folios after checkout, missing tax profiles, invoice-link mismatch, failed sync, duplicate sync keys, cashier variance, and unresolved restaurant stock posting.

## Payment correction

Only these automatic actions exist:

- delete a Draft Payment Entry;
- create an idempotent refund **draft** through the existing hotel refund function.

Submitted vouchers are not edited directly. The system does not create Journal Entry adjustments.

## Integration maturity

Definitions explicitly distinguish Shipped, Adapter, Recipe, and Planned. Live status requires eligible maturity and all mandatory checks Passed.

## Compatibility

- Frappe: v16 release line.
- ERPNext: v16 release line.
- Upgrade path: RC5 to RC6 via `bench migrate`.
- No ERPNext core modification.

## Status

RC6 is a staging candidate. Real Frappe/ERPNext bench migration, GL/AR/Stock Ledger reconciliation, concurrent correction execution, and Production Gate sign-off remain required.
