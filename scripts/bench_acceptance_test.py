"""Runtime acceptance test for Coffee Processing.

Run from the bench:
    bench --site coffee.localhost execute coffee_processing.scripts.bench_acceptance_test.run

The test is read-only: it validates installed metadata/master data and the
mathematical invariants used by processing/costing. It does not create stock
transactions.
"""
import frappe
from pathlib import Path


def check(label, condition):
    if not condition:
        raise AssertionError(label)
    print("[OK]", label)


def run():
    company = "الاهدل للبن"
    check("Company exists", frappe.db.exists("Company", company))
    check("Company currency is YER", frappe.db.get_value("Company", company, "default_currency") == "YER")
    check("Perpetual inventory enabled", int(frappe.db.get_value("Company", company, "enable_perpetual_inventory") or 0) == 1)

    for cur in ("YER", "SAR", "USD"):
        check(f"Currency {cur}", frappe.db.exists("Currency", cur))

    for dt, minimum in (("Coffee Operation Master", 9), ("Coffee Process Route", 2), ("Coffee Grade Master", 3), ("Coffee Process Order", 0), ("Coffee Batch", 0)):
        if minimum:
            check(f"{dt} master data", frappe.db.count(dt) >= minimum)
        else:
            check(f"{dt} DocType", frappe.db.exists("DocType", dt))

    for role in (
        "Coffee Processing Manager", "Coffee Receiving User", "Coffee Batch User",
        "Coffee Sorting User", "Coffee Fermentation User", "Coffee Drying User",
        "Coffee Hulling User", "Coffee Grading User", "Coffee Cupping User",
        "Coffee Packaging User", "Coffee Blending User", "Coffee Accountant",
    ):
        check(f"Role {role}", frappe.db.exists("Role", role))

    for field in ("region", "coffee_region", "coffee_city", "coffee_altitude_m", "coffee_type"):
        check(f"Supplier field {field}", frappe.db.exists("Custom Field", {"dt": "Supplier", "fieldname": field}))

    for region in ("برع", "جبل راس", "بن الحارث", "حراز", "النادرة", "كشر"):
        check(f"Supplier Region {region}", frappe.db.exists("Supplier Region", region))

    for name in ("حسابات بنكية متعددة العملات - ALC", "محافظ إلكترونية متعددة العملات - ALC"):
        check(f"Account group {name}", frappe.db.exists("Account", name))

    # Critical parent-child account invariants.
    account_checks = {
        "أصول متداولة - ALC": "استخدام الاموال (الأصول) - ALC",
        "اصول المخزون - ALC": "أصول متداولة - ALC",
        "حسابات مصرفية - ALC": "أصول متداولة - ALC",
        "مخزون البن تحت المعالجة - ALC": "البن تحت المعالجة - ALC",
    }
    for child, parent in account_checks.items():
        check(f"Account parent {child}", frappe.db.get_value("Account", child, "parent_account") == parent)

    for cur in ("YER", "SAR", "USD"):
        check(f"Bank {cur}", frappe.db.exists("Account", f"بنك {cur} - ALC"))
        check(f"Wallet {cur}", frappe.db.exists("Account", f"محفظة إلكترونية {cur} - ALC"))

    # Operation/route coverage.
    operations = {r[0] for r in frappe.get_all("Coffee Operation Master", pluck="name")}
    required_ops = {"RECEIVING", "SORTING", "FERMENTATION", "DRYING", "HULLING", "GRADING", "CUPPING", "PACKAGING", "BLENDING"}
    check("All 9 processing operations exist", required_ops.issubset(operations))

    for route_name in frappe.get_all("Coffee Process Route", pluck="name"):
        route = frappe.get_doc("Coffee Process Route", route_name)
        sequences = [int(s.sequence) for s in route.steps]
        check(f"Route {route_name} has ordered steps", sequences == sorted(sequences) and len(sequences) == len(set(sequences)))
        check(f"Route {route_name} steps have valid operations", all(s.operation in operations for s in route.steps))

    # Packaged dashboard/icon assets.
    root = Path(frappe.get_app_path("coffee_processing"))
    for rel in (
        "coffee_processing/coffee_processing_dashboard",
        "coffee_processing/dashboard_chart",
        "coffee_processing/workspace",
        "public/images/coffee_processing_logo.svg",
    ):
        check(f"Asset {rel}", (root / rel).exists())

    # Full dashboard and operation-interface coverage.
    for dt in (
        "Coffee Receiving Order", "Coffee Sorting Order",
        "Coffee Fermentation Order", "Coffee Drying Order",
        "Coffee Peeling Service", "Coffee Grading Order",
        "Coffee Cupping", "Coffee Blend Order", "Coffee Packaging Order",
        "Coffee Process Trial", "Coffee Fermentation Barrel", "Coffee Drying Bed",
    ):
        check(f"Operation/interface DocType {dt}", frappe.db.exists("DocType", dt))

    dashboard_name = "Coffee Dashboard"
    check("Coffee Dashboard exists", frappe.db.exists("Dashboard", dashboard_name))
    for number_card in (
        "Coffee Total Batches", "Coffee Current Qty", "Coffee Inventory Value",
        "Coffee In Progress Orders", "Coffee Completed Orders",
        "Coffee Input Qty", "Coffee Output Qty", "Coffee Loss Qty", "Coffee Production Plans",
    ):
        check(f"Number Card {number_card}", frappe.db.exists("Number Card", number_card))

    for dt in ("Coffee Fermentation Barrel", "Coffee Drying Bed"):
        check(f"Resource master {dt}", frappe.db.exists("DocType", dt))

    # Supplier metadata required by the procurement/origin workflow.
    for field in ("coffee_region", "coffee_city", "coffee_altitude_m", "coffee_type"):
        check(f"Supplier origin field {field}", frappe.db.exists("Custom Field", {"dt": "Supplier", "fieldname": field}))

    print("ALL BENCH ACCEPTANCE CHECKS PASSED")
