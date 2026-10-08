# Coffee Processing — Multi-Input Stock Entry Checkpoint

Date: 2026-10-08
App: coffee_processing 0.0.3
Site: coffee.localhost

## Result

FULL MULTI-INPUT STOCK ENTRY INTEGRATION TEST: PASSED

POST-ROLLBACK VERIFICATION: PASSED

## Scenario

Process Order:
CPO-2026-00001

Operation:
SORTING

Route:
مسار البن التجاري القياسي

Route Step:
2

Company:
الاهدل للبن

Branch:
الرئيسي - الاهدل للبن

## Inputs

CB-2026-00004
Quantity: 5 kg
Input cost: 12,000

CB-2026-00008
Quantity: 5 kg
Input cost: 12,000

Total input:
10 kg

Total input cost:
24,000

## Output

Coffee Batch:
CB-2026-00009

Quantity:
8 kg

Rate:
3,000

ERPNext Batch:
CPO-BATCH-2026-00002

Parent Batch:
None

Status:
In Process

## Stock Entry

Stock Entry:
MAT-STE-2026-00006

Type:
Repack

Docstatus:
1 — Submitted

Items:
3

## Multi-Input Traceability

Coffee Batch Source rows:
2

CB-2026-00004
Consumed: 5 kg
Cost: 12,000

CB-2026-00008
Consumed: 5 kg
Cost: 12,000

Trace quantity:
10 kg

Trace cost:
24,000

## Source Batch Quantities

CB-2026-00004:
700 kg -> 695 kg

CB-2026-00008:
300 kg -> 295 kg

## Rollback Verification

CB-2026-00004:
700 kg

CB-2026-00008:
300 kg

Test output Coffee Batch CB-2026-00009:
Not found

Test ERPNext Batch CPO-BATCH-2026-00002:
Not found

Test Stock Entry MAT-STE-2026-00006:
Not found

Test Coffee Batch Source rows:
0

Bin:
Item 001 / CPW

Actual Qty:
1000 kg

Reserved Qty:
0 kg

## Final Acceptance

PASS

No permanent test data detected.

The multi-input Stock Entry integration and Coffee Batch Source traceability
are verified against the real Frappe/ERPNext database and successfully rolled back.
