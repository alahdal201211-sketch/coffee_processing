"""Read-only acceptance test for an installed Coffee Processing site.

Run:
    bench --site coffee.localhost execute coffee_processing.scripts.full_site_acceptance_test.run

This script deliberately does not submit transactions. It validates that the
installed metadata/master data is ready for the manual transaction matrix.
"""
import frappe
from frappe import _


def check(label, condition):
    if not condition:
        raise AssertionError(label)
    print("[PASS]", label)


def run():
    company = "الاهدل للبن"
    check("Company exists", frappe.db.exists("Company", company))

    # Core operations
    required = ["RECEIVING", "SORTING", "FERMENTATION", "DRYING", "HULLING", "GRADING", "CUPPING", "PACKAGING", "BLENDING"]
    ops = set(frappe.get_all("Coffee Operation Master", pluck="operation_code"))
    check("All processing operations exist", set(required).issubset(ops))

    # Sorting rules
    check("Sorting allows multiple inputs", int(frappe.db.get_value("Coffee Operation Master", "SORTING", "allow_multiple_inputs") or 0) == 1)
    check("Sorting does not require quality", int(frappe.db.get_value("Coffee Operation Master", "SORTING", "requires_quality") or 0) == 0)

    # Resources
    barrels = frappe.db.count("Coffee Fermentation Barrel", {"active": 1})
    beds = frappe.db.count("Coffee Drying Bed", {"active": 1})
    check("At least 245 fermentation barrels", barrels >= 245)
    check("At least 320 drying beds", beds >= 320)
    check("Fermentation barrel capacity 160 kg", float(frappe.db.get_value("Coffee Fermentation Barrel", {"code": "BARREL-001"}, "capacity_kg") or 0) == 160)
    check("Drying bed capacity 50 kg", float(frappe.db.get_value("Coffee Drying Bed", {"code": "BED-001"}, "capacity_kg") or 0) == 50)

    # Routes
    for route_name in frappe.get_all("Coffee Process Route", pluck="name"):
        route = frappe.get_doc("Coffee Process Route", route_name)
        for step in route.steps:
            if step.operation == "SORTING":
                check(f"{route_name}: Sorting quality disabled", int(step.requires_quality or 0) == 0)
            elif step.operation == "FERMENTATION":
                check(f"{route_name}: Fermentation 1-5 days", int(step.minimum_days or 0) == 1 and int(step.maximum_days or 0) == 5)
            elif step.operation == "DRYING":
                check(f"{route_name}: Drying 25-30 days", int(step.minimum_days or 0) == 25 and int(step.maximum_days or 0) == 30)

    # Schema checks
    for dt, field in (
        ("Coffee Sorting Order", "cost_allocation_method"),
        ("Coffee Fermentation Order", "source_warehouse"),
        ("Coffee Fermentation Order", "target_warehouse"),
        ("Coffee Fermentation Order", "resource_allocations"),
        ("Coffee Drying Order", "source_warehouse"),
        ("Coffee Drying Order", "target_warehouse"),
        ("Coffee Drying Order", "resource_allocations"),
        ("Coffee Daily Monitoring", "drying_order"),
        ("Coffee Packaging Order", "stock_entry"),
    ):
        check(f"Field {dt}.{field}", frappe.db.exists("DocField", {"parent": dt, "fieldname": field}))

    # Critical items
    for code in ("COF-002", "COF-003", "102", "COF-008", "COF-023", "COF-027", "COF-031", "COF-035", "COF-039"):
        check(f"Item {code}", frappe.db.exists("Item", code))

    print("SITE METADATA ACCEPTANCE: PASS")
