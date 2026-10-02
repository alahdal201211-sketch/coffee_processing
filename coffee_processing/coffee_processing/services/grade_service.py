# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import flt


def get_grade_batches(coffee_type=None, grade=None, company=None, branch=None):
    filters = {"is_grade_batch": 1}
    if coffee_type:
        filters["coffee_type"] = coffee_type
    if grade:
        filters["coffee_grade"] = grade
    if company:
        filters["company"] = company
    if branch:
        filters["branch"] = branch

    return frappe.get_all(
        "Coffee Batch", filters=filters,
        fields=["name", "custom_item_code", "item_name", "coffee_grade",
                "coffee_type", "qty", "cost_per_kg", "total_value",
                "current_warehouse", "company", "branch", "status"]
    )


def get_grade_stock_summary(company=None, branch=None):
    conditions = "WHERE is_grade_batch = 1 AND qty > 0"
    params = {}
    if company:
        conditions += " AND company = %(company)s"
        params["company"] = company
    if branch:
        conditions += " AND branch = %(branch)s"
        params["branch"] = branch

    return frappe.db.sql(f"""
        SELECT
            coffee_type,
            coffee_grade,
            COUNT(*) as batch_count,
            SUM(qty) as total_qty,
            SUM(total_value) as total_value,
            AVG(cost_per_kg) as avg_cost_per_kg
        FROM `tabCoffee Batch`
        {conditions}
        GROUP BY coffee_type, coffee_grade
        ORDER BY coffee_type, coffee_grade
    """, params, as_dict=True)


def get_grade_yield(parent_batch_name):
    parent = frappe.get_doc("Coffee Batch", parent_batch_name)
    children = frappe.get_all(
        "Coffee Batch",
        filters={"parent_batch": parent_batch_name, "is_grade_batch": 1},
        fields=["name", "custom_item_code", "coffee_grade", "coffee_type",
                "qty", "total_value"]
    )
    total_output = sum(flt(c.qty) for c in children)
    for c in children:
        c["yield_percentage"] = (flt(c.qty) / total_output * 100) if total_output else 0
    return {
        "parent": parent.name,
        "parent_qty": parent.qty,
        "total_output": total_output,
        "grades": children,
    }
