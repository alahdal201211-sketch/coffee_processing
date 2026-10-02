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

    company_abbr = frappe.db.get_value("Company", company, "abbr")

    bank_group = f"1200 - حسابات مصرفية - {company_abbr}"
    check(f"Account group {bank_group}", frappe.db.exists("Account", bank_group))

    for name in (
        f"بنك YER - {company_abbr}",
        f"بنك SAR - {company_abbr}",
        f"بنك USD - {company_abbr}",
        f"محفظة إلكترونية YER - {company_abbr}",
        f"محفظة إلكترونية SAR - {company_abbr}",
        f"محفظة إلكترونية USD - {company_abbr}",
    ):
        check(f"Currency account {name}", frappe.db.exists("Account", name))

    # Critical parent-child account invariants.
    company_abbr = frappe.db.get_value("Company", company, "abbr")

    account_checks = {
        f"1100-1600 - أصول متداولة - {company_abbr}":
            f"1000 - استخدام الاموال (الأصول) - {company_abbr}",

        f"1200 - حسابات مصرفية - {company_abbr}":
            f"1100-1600 - أصول متداولة - {company_abbr}",
    }

    for child, parent in account_checks.items():
        check(
            f"Account parent {child}",
            frappe.db.get_value("Account", child, "parent_account") == parent
        )

    for cur in ("YER", "SAR", "USD"):
        check(f"Bank {cur}", frappe.db.exists("Account", f"بنك {cur} - {company_abbr}"))
        check(f"Wallet {cur}", frappe.db.exists("Account", f"محفظة إلكترونية {cur} - {company_abbr}"))

    # Operation/route coverage.
    operations = {
        r.operation_code
        for r in frappe.get_all(
            "Coffee Operation Master",
            fields=["operation_code"]
        )
        if r.operation_code
    }

    required_ops = {
        "RECEIVING",
        "SORTING",
        "FERMENTATION",
        "DRYING",
        "HULLING",
        "GRADING",
        "CUPPING",
        "PACKAGING",
        "BLENDING",
    }

    check(
        "All 9 processing operations exist",
        required_ops.issubset(operations)
    )

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

    # Current packaged KPI cards.
    expected_number_cards = [
        "إجمالي دفعات البن",
        "دفعات قيد المعالجة",
        "دفعات مكتملة",
        "دفعات جاهزة للمعالجة",
        "إجمالي كمية الدفعات",
        "إجمالي قيمة الدفعات",
        "إجمالي أوامر المعالجة",
        "أوامر قيد التنفيذ",
        "أوامر مكتملة",
        "أوامر بانتظار الموافقة",
        "أوامر فرق تحتاج موافقة",
        "إجمالي تكلفة المعالجة",
    ]

    for number_card in expected_number_cards:
        check(
            f"Number Card {number_card}",
            frappe.db.exists("Number Card", number_card)
        )

    actual_number_cards = frappe.get_all(
        "Number Card",
        filters={"module": "Coffee Processing"},
        pluck="name",
        order_by="name asc",
    )

    for legacy_card in (
        "Coffee Total Batches",
        "Coffee Current Qty",
        "Coffee Inventory Value",
        "Coffee In Progress Orders",
        "Coffee Completed Orders",
        "Coffee Input Qty",
        "Coffee Output Qty",
        "Coffee Loss Qty",
        "Coffee Production Plans",
    ):
        check(
            f"Legacy Number Card removed: {legacy_card}",
            legacy_card not in actual_number_cards
        )

    dashboard = frappe.get_doc("Dashboard", dashboard_name)

    dashboard_cards = [row.card for row in dashboard.cards]

    check(
        "Coffee Dashboard has exactly 12 KPI cards",
        dashboard_cards == expected_number_cards
    )

    expected_dashboard_charts = [
        "حالة دفعات البن",
        "حالة أوامر المعالجة",
        "أنواع البن",
        "العمليات المنفذة",
        "الكمية الداخلة حسب العملية",
        "الكمية الخارجة حسب العملية",
        "الفاقد حسب العملية",
        "تكلفة المعالجة حسب العملية",
    ]

    dashboard_charts = [row.chart for row in dashboard.charts]

    check(
        "Coffee Dashboard has exactly 8 charts",
        dashboard_charts == expected_dashboard_charts
    )

    legacy_links = frappe.db.sql(
        """
        SELECT parent, card
        FROM `tabNumber Card Link`
        WHERE card IN (
            'Coffee Total Batches',
            'Coffee Current Qty',
            'Coffee Inventory Value',
            'Coffee In Progress Orders',
            'Coffee Completed Orders',
            'Coffee Input Qty',
            'Coffee Output Qty',
            'Coffee Loss Qty',
            'Coffee Production Plans'
        )
        """,
        as_dict=True,
    )

    check(
        "No legacy Number Card dashboard links",
        not legacy_links
    )

    for dt in ("Coffee Fermentation Barrel", "Coffee Drying Bed"):
        check(f"Resource master {dt}", frappe.db.exists("DocType", dt))

    # Supplier metadata required by the procurement/origin workflow.
    for field in ("coffee_region", "coffee_city", "coffee_altitude_m", "coffee_type"):
        check(f"Supplier origin field {field}", frappe.db.exists("Custom Field", {"dt": "Supplier", "fieldname": field}))

    print("ALL BENCH ACCEPTANCE CHECKS PASSED")
