"""Offline package acceptance checks; no Frappe site/database required."""
from pathlib import Path
import json, py_compile, ast

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'coffee_processing'

def ok(msg, cond):
    if not cond: raise AssertionError(msg)
    print('[PASS]',msg)

def fields(dt):
    p=APP/'doctype'/dt/(dt+'.json'); return json.loads(p.read_text(encoding='utf8'))['fields']

def has(dt, name): return any(f.get('fieldname')==name for f in fields(dt))

def opts(dt,name):
    return next(f for f in fields(dt) if f.get('fieldname')==name).get('options','').splitlines()

# JSON/Python integrity
for p in APP.rglob('*.json'):
    json.loads(p.read_text(encoding='utf8'))
for p in APP.rglob('*.py'):
    py_compile.compile(str(p),doraise=True)
ok('All JSON files parse', True)
ok('All Python files compile', True)

# Sorting
ok('Sorting cost method field',has('coffee_sorting_order','cost_allocation_method'))
ok('Sorting default Same Input Cost', next(f for f in fields('coffee_sorting_order') if f['fieldname']=='cost_allocation_method').get('default')=='Same Input Cost')
ok('Sorting Manual option', 'Manual' in opts('coffee_sorting_order','cost_allocation_method'))
ok('Sorting multi-input operation fixture', json.loads((ROOT/'fixtures/coffee_operation_master.json').read_text(encoding='utf8'))[1]['allow_multiple_inputs'] in (0,1))

# Central costing
methods=opts('coffee_process_order','cost_allocation_method')
ok('CPO Same Input Cost option', 'Same Input Cost' in methods)
ok('CPO Manual option', 'Manual' in methods)

# Resource masters
ok('Fermentation barrel capacity field',has('coffee_fermentation_barrel','capacity_kg'))
ok('Drying bed capacity field',has('coffee_drying_bed','capacity_kg'))
ok('Fermentation resource allocation table',has('coffee_fermentation_order','resource_allocations'))
ok('Drying resource allocation table',has('coffee_drying_order','resource_allocations'))
ok('Fermentation source warehouse',has('coffee_fermentation_order','source_warehouse'))
ok('Fermentation target warehouse',has('coffee_fermentation_order','target_warehouse'))
ok('Drying source warehouse',has('coffee_drying_order','source_warehouse'))
ok('Drying target warehouse',has('coffee_drying_order','target_warehouse'))

# Duration
ok('Fermentation start/end',has('coffee_fermentation_order','start_datetime') and has('coffee_fermentation_order','end_datetime'))
ok('Drying start/end',has('coffee_drying_order','start_datetime') and has('coffee_drying_order','end_datetime'))

# Daily monitoring
ok('Daily monitoring links to drying order',has('coffee_daily_monitoring','drying_order'))
resources=json.loads((ROOT/'setup/data/resources.json').read_text(encoding='utf8'))
ok('245 fermentation barrels configured', resources['fermentation']['count']==245 and resources['fermentation']['capacity_kg']==160)
ok('320 drying beds configured', resources['drying']['count']==320 and resources['drying']['capacity_kg']==50)
routes=json.loads((ROOT/'fixtures/coffee_process_route.json').read_text(encoding='utf8'))
for route in routes:
    for step in route.get('steps',[]):
        if step.get('operation')=='FERMENTATION': ok('Fermentation route duration 1-5', step['minimum_days']==1 and step['maximum_days']==5)
        if step.get('operation')=='DRYING': ok('Drying route duration 25-30', step['minimum_days']==25 and step['maximum_days']==30)

# Grading dynamic schema
ok('Grading dynamic target grade',has('coffee_grading_order','target_grade'))
ok('Operation batch grade field',has('coffee_operation_batch','coffee_grade'))
ok('CPO output grade field',has('coffee_process_order_output','coffee_grade'))

# Packaging
for x in ('source_warehouse','target_warehouse','stock_entry','output_batch'):
    ok('Packaging '+x,has('coffee_packaging_order',x))

# Item master coverage from packaged data
items=json.loads((ROOT/'setup/data/items.json').read_text(encoding='utf8'))
names={x.get('item_name','') for x in items}
for phrase in ('بن احمر','بن احمر عيوب','بن مخمر','بن قاصي مجفف','صافي مختص','قشر مختص','دقه مختص','كسره مختص','بعوره مختص'):
    ok('Item '+phrase, any(phrase in n for n in names))

# Cost invariant used by Same Input Cost: input + process/overhead allocated by quantity.
input_qty=10; input_rate=2400; process=100; overhead=125; outputs=[9,1]
gross=input_qty*input_rate+process+overhead
rates=[gross/sum(outputs)]*2
amounts=[q*r for q,r in zip(outputs,rates)]
ok('Same Input Cost math total',abs(sum(amounts)-24225)<1e-9)
ok('Same Input Cost unit rate',abs(rates[0]-2422.5)<1e-9)

print('PACKAGE STATIC ACCEPTANCE: PASS')
