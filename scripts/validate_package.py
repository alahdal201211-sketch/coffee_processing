#!/usr/bin/env python3
import ast, json, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
errors=[]; checks=[]
def ok(label, value=True):
    checks.append((label, bool(value)))
    if not value: errors.append(label)
for p in ROOT.rglob('*.py'):
    try: ast.parse(p.read_text(encoding='utf-8'))
    except Exception as e: errors.append(f'Python syntax: {p}: {e}')
for p in ROOT.rglob('*.json'):
    try: json.loads(p.read_text(encoding='utf-8'))
    except Exception as e: errors.append(f'JSON: {p}: {e}')
# Dashboard integrity: these are the original dashboard/workspace artifacts and must remain present.
required=[
 ROOT/'coffee_processing/coffee_processing/coffee_processing_dashboard',
 ROOT/'coffee_processing/coffee_processing/dashboard_chart',
 ROOT/'coffee_processing/coffee_processing/workspace',
]
for p in required: ok(f'preserved: {p.relative_to(ROOT)}', p.exists())
# Master data checks
items=json.loads((ROOT/'coffee_processing/setup/data/items.json').read_text(encoding='utf8'))
ok('items non-empty', len(items)>100)
ok('unique item codes', len({x['item_code'] for x in items})==len(items))
ok('unique item names', len({x['item_name'] for x in items})==len(items))
for f in ['accounts.json','warehouses.json','cost_centers.json','item_groups.json','company.json','business_master.json']:
    ok(f'master data: {f}', (ROOT/'coffee_processing/setup/data'/f).exists())
print(f'Checks: {len(checks)}')
for label, passed in checks: print('[OK]' if passed else '[FAIL]', label)
if errors:
    print('\n'.join(errors)); sys.exit(1)
print('ALL STATIC CHECKS PASSED')
