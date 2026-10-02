"""Full offline acceptance audit for the Coffee Processing package.

This test does not require a running Bench. It validates the packaged metadata,
interfaces, dashboard assets and the supplied SQL backup schema/data footprint.
"""
from __future__ import annotations
import gzip, json, re, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "coffee_processing"

def fail(msg):
    print("[FAIL]", msg); raise SystemExit(1)
def ok(msg): print("[OK]", msg)

def load_json(p):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e: fail(f"Invalid JSON: {p}: {e}")

required = {
    "Coffee Batch": APP/"coffee_processing/coffee_processing/doctype/coffee_batch/coffee_batch.json",
    "Coffee Process Order": APP/"coffee_processing/coffee_processing/doctype/coffee_process_order/coffee_process_order.json",
    "Coffee Receiving Order": APP/"coffee_processing/coffee_processing/doctype/coffee_receiving_order/coffee_receiving_order.json",
    "Coffee Sorting Order": APP/"coffee_processing/coffee_processing/doctype/coffee_sorting_order/coffee_sorting_order.json",
    "Coffee Fermentation Order": APP/"coffee_processing/coffee_processing/doctype/coffee_fermentation_order/coffee_fermentation_order.json",
    "Coffee Drying Order": APP/"coffee_processing/coffee_processing/doctype/coffee_drying_order/coffee_drying_order.json",
    "Coffee Peeling Service": APP/"coffee_processing/coffee_processing/doctype/coffee_peeling_service/coffee_peeling_service.json",
    "Coffee Grading Order": APP/"coffee_processing/coffee_processing/doctype/coffee_grading_order/coffee_grading_order.json",
    "Coffee Cupping": APP/"coffee_processing/coffee_processing/doctype/coffee_cupping/coffee_cupping.json",
    "Coffee Blend Order": APP/"coffee_processing/coffee_processing/doctype/coffee_blend_order/coffee_blend_order.json",
    "Coffee Packaging Order": APP/"coffee_processing/coffee_processing/doctype/coffee_packaging_order/coffee_packaging_order.json",
    "Coffee Process Trial": APP/"coffee_processing/coffee_processing/doctype/coffee_process_trial/coffee_process_trial.json",
    "Coffee Production Plan": APP/"coffee_processing/coffee_processing/doctype/coffee_production_plan/coffee_production_plan.json",
    "Coffee Fermentation Barrel": APP/"coffee_processing/coffee_processing/doctype/coffee_fermentation_barrel/coffee_fermentation_barrel.json",
    "Coffee Drying Bed": APP/"coffee_processing/coffee_processing/doctype/coffee_drying_bed/coffee_drying_bed.json",
}
for name,p in required.items():
    if not p.exists(): fail(f"Missing DocType: {name}")
    o=load_json(p); assert o.get("name")==name
ok(f"Required DocTypes present: {len(required)}")

# Required fields and links
for dt, fields in {
    "Coffee Batch":{"supplier","route","current_warehouse","qty","valuation_rate","cost_per_kg","total_value"},
    "Coffee Process Order":{"operation","inputs","outputs","input_qty_total","output_qty_total","loss_qty","variance_qty","output_cost_total"},
    "Coffee Receiving Order":{"supplier","purchase_receipt","inputs","outputs"},
    "Coffee Fermentation Order":{"storage_unit","barrel"},
    "Coffee Drying Order":{"storage_unit","drying_bed"},
    "Coffee Process Trial":{"steps","status","cupping_score","trial_qty","production_plan"},
    "Coffee Production Plan":{"trial","planned_qty","scale_factor","steps","status"},
    "Coffee Packaging Order":{"input_qty","number_of_packages","target_item_code","output_qty"},
}.items():
    o=load_json(required[dt]); got={f.get('fieldname') for f in o.get('fields',[])}
    missing=fields-got
    if missing: fail(f"{dt} missing fields: {sorted(missing)}")
ok("Critical workflow fields and barrel/bed links present")

# Dashboard completeness
# Legacy dashboard asset intentionally removed; live dashboard is ensured by setup/install.py
if not D.exists(): fail("Coffee Dashboard JSON missing")
dash=load_json(D)
if len(dash.get("charts",[])) < 10: fail("Coffee Dashboard has fewer than 10 charts")
if len(dash.get("number_cards",[])) < 9: fail("Coffee Dashboard has fewer than 8 number cards")
ok(f"Dashboard: {len(dash['number_cards'])} number cards + {len(dash['charts'])} charts")

# Number cards point to existing doctypes/fields
cards_dir=APP/"coffee_processing/number_card"
for c in dash["number_cards"]:
    p=cards_dir/c.lower().replace(' ','_')/((c.lower().replace(' ','_'))+'.json')
    if not p.exists(): fail(f"Missing number card file: {c}")
    card=load_json(p)
    if card.get("document_type") not in required and card.get("document_type") not in ["Coffee Storage Unit","Coffee Cupping"]:
        fail(f"Number card {c} references unknown DocType {card.get('document_type')}")
ok("All dashboard number-card assets are present")

# Workspace coverage
ws=APP/"coffee_processing/coffee_processing/workspace/coffee_processing/coffee_processing.json"
if not ws.exists(): fail("Coffee workspace missing")
w=load_json(ws)
content=w.get('content','')
for label in ["استلام البن","الفرز","التخمير","التجفيف","التقشير وخدمة الغير","التصنيف والتنقية","التذوق والتقييم","الخلط","التعبئة","براميل التخمير","سراير التجفيف","التجارب الإنتاجية","خطط الإنتاج"]:
    if label not in content: fail(f"Workspace missing interface: {label}")
ok("Workspace covers all operation interfaces and resources")

# Permission coverage
for dt in ["Coffee Batch","Coffee Process Order","Coffee Receiving Order","Coffee Sorting Order","Coffee Fermentation Order","Coffee Drying Order","Coffee Peeling Service","Coffee Grading Order","Coffee Cupping","Coffee Blend Order","Coffee Packaging Order"]:
    o=load_json(required[dt])
    roles={p.get('role') for p in o.get('permissions',[])}
    if "Coffee Processing Manager" not in roles and "System Manager" not in roles: fail(f"{dt} lacks manager permission")
ok("Operational DocTypes have manager permissions")

# Optional SQL backup consistency audit
sql_candidates=[__import__("pathlib").Path("/mnt/data/20260930_202451-coffee_localhost-database.sql.gz")]
if sql_candidates:
    sql=sql_candidates[0]
    with gzip.open(sql,'rb') as f: text=f.read().decode('utf-8','replace')
    tables=set(re.findall(r'CREATE TABLE `([^`]+)`',text))
    for dt in ["Coffee Batch","Coffee Process Order","Coffee Process Trial","Coffee Fermentation Order","Coffee Drying Order","Coffee Storage Unit"]:
        if "tab"+dt not in tables: fail(f"SQL backup lacks table tab{dt}")
    ok(f"SQL backup schema contains core Coffee tables: {sql.name}")
else:
    print("[WARN] SQL backup not found beside package; schema check skipped")

print("FULL OFFLINE ACCEPTANCE PASSED")
