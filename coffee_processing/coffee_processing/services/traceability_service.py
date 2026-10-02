# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import flt


def get_ancestors(batch_name, max_depth=50):
    ancestors = []
    current_name = batch_name
    depth = 0
    while current_name and depth < max_depth:
        batch = frappe.db.get_value(
            "Coffee Batch", current_name,
            ["name", "parent_batch"], as_dict=True
        )
        if not batch or not batch.parent_batch:
            break
        parent = frappe.db.get_value(
            "Coffee Batch", batch.parent_batch,
            ["name", "custom_item_code", "coffee_grade", "source_type",
             "supplier", "status"],
            as_dict=True
        )
        if not parent:
            break
        depth += 1
        ancestors.append({"level": depth, "batch": parent})
        current_name = parent.name
    return ancestors


def get_descendants(batch_name, max_depth=50):
    descendants = []

    def _recurse(parent_name, level):
        if level > max_depth:
            return
        children = frappe.get_all(
            "Coffee Batch",
            filters={"parent_batch": parent_name},
            fields=["name", "custom_item_code", "coffee_grade", "status",
                    "source_type", "coffee_type", "is_grade_batch"],
        )
        for child in children:
            descendants.append({"level": level, "batch": child})
            _recurse(child.name, level + 1)

    _recurse(batch_name, 1)
    return descendants


def get_batch_lineage(batch_name):
    batch = frappe.get_doc("Coffee Batch", batch_name)
    return {
        "batch": {
            "name": batch.name, "custom_item_code": batch.custom_item_code,
            "item_name": batch.item_name,
            "coffee_type": batch.coffee_type, "coffee_grade": batch.coffee_grade,
            "status": batch.status, "source_type": batch.source_type,
            "current_step": batch.current_step,
            "current_operation": batch.current_operation,
            "is_grade_batch": batch.is_grade_batch,
        },
        "ancestors": get_ancestors(batch_name),
        "descendants": get_descendants(batch_name),
    }


def get_backward_trace(batch_name):
    chain = []
    current = frappe.get_doc("Coffee Batch", batch_name)
    while current:
        chain.append({
            "name": current.name, "custom_item_code": current.custom_item_code,
            "grade": current.coffee_grade, "source_type": current.source_type,
            "status": current.status,
        })
        if not current.parent_batch:
            break
        current = frappe.get_doc("Coffee Batch", current.parent_batch)

    root = frappe.get_doc("Coffee Batch", batch_name)
    while root.parent_batch:
        root = frappe.get_doc("Coffee Batch", root.parent_batch)

    return {
        "chain": chain,
        "supplier": root.supplier,
        "purchase_receipt": root.purchase_receipt,
    }


def get_processing_timeline(batch_name):
    events = []

    # Coffee Batch is linked to the child tables, not directly
    # to Coffee Process Order.
    input_orders = frappe.get_all(
        "Coffee Process Order Input",
        filters={"coffee_batch": batch_name},
        pluck="parent",
    )

    output_orders = frappe.get_all(
        "Coffee Process Order Output",
        filters={"coffee_batch": batch_name},
        pluck="parent",
    )

    order_names = list(dict.fromkeys(input_orders + output_orders))

    if order_names:
        orders = frappe.get_all(
            "Coffee Process Order",
            filters={
                "name": ["in", order_names],
                "docstatus": 1,
            },
            fields=[
                "name",
                "operation",
                "posting_date",
                "status",
                "input_qty_total",
                "output_qty_total",
                "variance_qty",
            ],
        )

        for order in orders:
            input_qty = flt(order.input_qty_total)
            output_qty = flt(order.output_qty_total)

            events.append({
                "type": "Processing",
                "date": order.posting_date,
                "reference": order.name,
                "description": (
                    f"{order.operation} - "
                    f"Input: {input_qty:g} KG - "
                    f"Output: {output_qty:g} KG"
                ),
                "status": order.status,
                "input_qty": input_qty,
                "output_qty": output_qty,
                "variance_qty": flt(order.variance_qty),
            })

    samples = frappe.get_all(
        "Coffee Sample",
        filters={"coffee_batch": batch_name, "docstatus": 1},
        fields=[
            "name",
            "sample_no",
            "sample_type",
            "sample_date",
            "status",
        ],
    )

    for sample in samples:
        events.append({
            "type": "Sample",
            "date": sample.sample_date,
            "reference": sample.sample_no or sample.name,
            "description": sample.sample_type,
            "status": sample.status,
        })

    cuppings = frappe.get_all(
        "Coffee Cupping",
        filters={"coffee_batch": batch_name, "docstatus": 1},
        fields=[
            "name",
            "cupping_no",
            "total_score",
            "cupping_result",
            "cupping_date",
            "status",
        ],
    )

    for cupping in cuppings:
        events.append({
            "type": "Cupping",
            "date": cupping.cupping_date,
            "reference": cupping.cupping_no or cupping.name,
            "description": (
                f"Score: {cupping.total_score} - "
                f"{cupping.cupping_result}"
            ),
            "status": cupping.status,
        })

    events.sort(key=lambda x: str(x.get("date") or ""))
    return events
