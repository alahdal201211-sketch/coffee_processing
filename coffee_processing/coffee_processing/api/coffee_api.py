# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt
from coffee_processing.coffee_processing.services.sequence_service import (
    get_next_executable_step, get_allowed_operations, validate_sequence, is_batch_completed,
)
from coffee_processing.coffee_processing.services.stock_service import (
    get_batch_qty, get_batch_value, get_batch_available_qty,
    get_batch_cost_per_kg, get_available_batches,
)
from coffee_processing.coffee_processing.services.batch_service import (
    split_batch, merge_batches,
)
from coffee_processing.coffee_processing.services.traceability_service import (
    get_batch_lineage, get_ancestors, get_descendants, get_backward_trace,
    get_processing_timeline,
)
from coffee_processing.coffee_processing.services.grade_service import (
    get_grade_batches as _get_grade_batches,
    get_grade_stock_summary as _get_grade_stock_summary,
    get_grade_yield as _get_grade_yield,
)


@frappe.whitelist()
def create_processing_order(
    coffee_batch,
    operation,
    planned_qty,
    source_warehouse=None,
    target_warehouse=None,
):
    """Create a Coffee Process Order using the current CPO model."""

    batch = frappe.get_doc("Coffee Batch", coffee_batch)

    result = validate_sequence(batch, operation)

    if not result["valid"]:
        frappe.throw(result["message"])

    planned_qty = flt(planned_qty)

    if planned_qty <= 0:
        frappe.throw(_("Planned quantity must be greater than zero."))

    source_warehouse = source_warehouse or batch.current_warehouse

    if not source_warehouse:
        frappe.throw(
            _("Source Warehouse is required for Coffee Process Order.")
        )

    next_step = result.get("next_step")

    if not next_step:
        frappe.throw(
            _("No executable route step was found for operation {0}.").format(
                operation
            )
        )

    if next_step.operation != operation:
        frappe.throw(
            _(
                "Operation {0} does not match the next route operation {1}."
            ).format(
                operation,
                next_step.operation,
            )
        )

    item_code = batch.custom_item_code

    if not item_code:
        frappe.throw(
            _("Coffee Batch {0} has no Item Code.").format(
                coffee_batch
            )
        )

    uom = frappe.db.get_value(
        "Item",
        item_code,
        "stock_uom",
    )

    if not uom:
        frappe.throw(
            _("Stock UOM is not defined for Item {0}.").format(
                item_code
            )
        )

    order = frappe.new_doc("Coffee Process Order")

    order.company = batch.company
    order.branch = batch.branch
    order.posting_date = frappe.utils.today()
    order.status = "Draft"

    order.route = batch.route
    order.route_step_sequence = next_step.sequence
    order.operation = operation

    order.source_warehouse = source_warehouse
    order.target_warehouse = (
        target_warehouse
        or source_warehouse
    )

    order.cost_center = batch.cost_center

    input_row = order.append("inputs", {})

    input_row.item = item_code
    input_row.coffee_batch = batch.name
    input_row.warehouse = source_warehouse
    input_row.qty = planned_qty
    input_row.uom = uom
    input_row.conversion_factor = 1

    if batch.erpnext_batch:
        input_row.batch_no = batch.erpnext_batch

    order.insert(ignore_permissions=True)

    return {
        "name": order.name,
        "status": order.status,
        "route": order.route,
        "route_step_sequence": order.route_step_sequence,
        "operation": order.operation,
        "coffee_batch": batch.name,
        "planned_qty": planned_qty,
    }


@frappe.whitelist()
def create_production_plan_from_trial(trial_name, planned_qty):
    trial = frappe.get_doc("Coffee Process Trial", trial_name)
    return trial.create_production_plan(planned_qty)


@frappe.whitelist()
def get_next_step(batch_name):
    batch = frappe.get_doc("Coffee Batch", batch_name)
    next_step = get_next_executable_step(batch)
    if not next_step:
        return {"completed": True,
                "message": _("Batch {0} has completed all processing steps").format(batch.name)}
    operation = frappe.get_doc("Coffee Operation Master", next_step.operation)
    return {
        "completed": False,
        "step": {
            "sequence": next_step.sequence,
            "operation": next_step.operation,
            "operation_name": operation.operation_name_ar,
            "required": next_step.required,
            "is_grading_operation": operation.is_grading_operation,
        },
        "allowed_operations": get_allowed_operations(batch),
    }


@frappe.whitelist()
def complete_processing_order(order_name):
    """Submit the current Coffee Process Order.

    The Coffee Process Order lifecycle is responsible for:
    validation, variance handling, Stock Entry creation/submission,
    Coffee Batch synchronization, and final completion status.
    """

    order = frappe.get_doc("Coffee Process Order", order_name)

    if order.docstatus == 2:
        frappe.throw(
            _("Coffee Process Order {0} is cancelled.").format(
                order.name
            )
        )

    if order.docstatus == 1:
        return {
            "name": order.name,
            "status": order.status,
            "docstatus": order.docstatus,
            "stock_entry": order.stock_entry,
            "stock_entry_status": order.stock_entry_status,
        }

    if order.approval_status == "Pending":
        frappe.throw(
            _("Coffee Process Order {0} is waiting for approval.").format(
                order.name
            )
        )

    order.submit()

    order.reload()

    return {
        "name": order.name,
        "status": order.status,
        "docstatus": order.docstatus,
        "stock_entry": order.stock_entry,
        "stock_entry_status": order.stock_entry_status,
    }


@frappe.whitelist()
def get_batch_info(batch_name):
    batch = frappe.get_doc("Coffee Batch", batch_name)
    return {
        "name": batch.name,
        "custom_item_code": batch.custom_item_code,
        "item_name": batch.item_name,
        "coffee_type": batch.coffee_type,
        "coffee_grade": batch.coffee_grade,
        "is_grade_batch": batch.is_grade_batch,
        "status": batch.status,
        "current_step": batch.current_step,
        "current_operation": batch.current_operation,
        "current_warehouse": batch.current_warehouse,
        "qty": batch.qty,
        "valuation_rate": batch.valuation_rate,
        "cost_per_kg": batch.cost_per_kg,
        "total_value": batch.total_value,
        "reserved_qty": batch.reserved_qty,
        "available_qty": batch.available_qty,
        "route": batch.route,
        "cost_center": batch.cost_center,
        "company": batch.company,
        "branch": batch.branch,
        "is_completed": is_batch_completed(batch),
    }


@frappe.whitelist()
def get_batch_processing_history(batch_name):
    """Return processing history from the current Coffee Process Order model."""

    if not frappe.db.exists("Coffee Batch", batch_name):
        frappe.throw(
            _("Coffee Batch {0} does not exist.").format(
                batch_name
            )
        )

    input_orders = frappe.get_all(
        "Coffee Process Order Input",
        filters={"coffee_batch": batch_name},
        fields=[
            "parent",
            "qty",
            "stock_qty",
            "item",
            "warehouse",
            "batch_no",
        ],
        order_by="creation asc",
    )

    output_orders = frappe.get_all(
        "Coffee Process Order Output",
        filters={"coffee_batch": batch_name},
        fields=[
            "parent",
            "qty",
            "stock_qty",
            "item",
            "warehouse",
            "batch_no",
            "output_type",
        ],
        order_by="creation asc",
    )

    order_names = set()

    for row in input_orders:
        order_names.add(row.parent)

    for row in output_orders:
        order_names.add(row.parent)

    if not order_names:
        return []

    orders = frappe.get_all(
        "Coffee Process Order",
        filters={"name": ["in", list(order_names)]},
        fields=[
            "name",
            "company",
            "branch",
            "posting_date",
            "status",
            "docstatus",
            "route",
            "route_step_sequence",
            "operation",
            "operation_code",
            "operation_name_ar",
            "input_qty_total",
            "output_qty_total",
            "loss_qty",
            "variance_qty",
            "variance_percent",
            "variance_status",
            "input_cost_total",
            "output_cost_total",
            "stock_entry",
            "stock_entry_status",
        ],
        order_by="posting_date asc, creation asc",
    )

    return orders


@frappe.whitelist()
def get_batch_lineage_api(batch_name):
    return get_batch_lineage(batch_name)


@frappe.whitelist()
def split_batch_api(batch_name, split_qty, new_warehouse=None):
    new_batch = split_batch(batch_name, flt(split_qty), new_warehouse)
    return {"name": new_batch.name}


@frappe.whitelist()
def merge_batches_api(batch_names, target_warehouse=None):
    import json
    if isinstance(batch_names, str):
        batch_names = json.loads(batch_names)
    merged = merge_batches(batch_names, target_warehouse)
    return {"name": merged.name}


@frappe.whitelist()
def get_available_batches_api(coffee_type=None, coffee_grade=None,
                               company=None, branch=None, is_grade_batch=None,
                               warehouse=None, status=None):
    return get_available_batches(coffee_type, coffee_grade, company, branch,
                                  is_grade_batch, warehouse, status)


@frappe.whitelist()
def create_sample_api(batch_name, sample_type, sample_qty, warehouse=None, notes=None):
    from coffee_processing.coffee_processing.services.quality_service import create_sample
    sample = create_sample(batch_name, sample_type, flt(sample_qty), warehouse, notes)
    return {"name": sample.name, "sample_no": sample.sample_no, "status": sample.status}


@frappe.whitelist()
def create_cupping_api(sample_name, cupping_data):
    import json
    if isinstance(cupping_data, str):
        cupping_data = json.loads(cupping_data)
    from coffee_processing.coffee_processing.services.quality_service import create_cupping
    cupping = create_cupping(sample_name, cupping_data)
    return {
        "name": cupping.name, "cupping_no": cupping.cupping_no,
        "total_score": cupping.total_score, "final_score": cupping.final_score,
        "cupping_result": cupping.cupping_result,
    }


@frappe.whitelist()
def get_batch_quality_status_api(batch_name):
    from coffee_processing.coffee_processing.services.quality_service import get_batch_quality_status
    return get_batch_quality_status(batch_name)


@frappe.whitelist()
def can_proceed_to_packaging_api(batch_name):
    from coffee_processing.coffee_processing.services.quality_service import can_proceed_to_packaging
    return can_proceed_to_packaging(batch_name)


@frappe.whitelist()
def approve_quality_api(batch_name):
    from coffee_processing.coffee_processing.services.quality_service import approve_quality
    batch = approve_quality(batch_name)
    return {"name": batch.name, "quality_status": batch.quality_status}


@frappe.whitelist()
def get_ancestors_api(batch_name):
    return get_ancestors(batch_name)


@frappe.whitelist()
def get_descendants_api(batch_name):
    return get_descendants(batch_name)


@frappe.whitelist()
def get_backward_trace_api(batch_name):
    return get_backward_trace(batch_name)


@frappe.whitelist()
def get_processing_timeline_api(batch_name):
    return get_processing_timeline(batch_name)


# ═══════════════════════════════════════════════════════════
# Grade-wise APIs
# ═══════════════════════════════════════════════════════════

@frappe.whitelist()
def get_grade_batches(coffee_type=None, grade=None, company=None, branch=None):
    return _get_grade_batches(coffee_type, grade, company, branch)


@frappe.whitelist()
def get_grade_stock_summary(company=None, branch=None):
    return _get_grade_stock_summary(company, branch)


@frappe.whitelist()
def get_grade_yield_api(batch_name):
    return _get_grade_yield(batch_name)


# ═══════════════════════════════════════════════════════════
# Item Code APIs (بديل Item)
# ═══════════════════════════════════════════════════════════

@frappe.whitelist()
def get_item_code_options(coffee_type=None, company=None):
    """الحصول على قائمة أكواد الأصناف المتاحة"""
    filters = {}
    if coffee_type:
        filters["coffee_type"] = coffee_type
    if company:
        filters["company"] = company

    return frappe.get_all(
        "Coffee Batch",
        filters=filters,
        fields=["custom_item_code", "item_name", "coffee_type", "coffee_grade"],
        group_by="custom_item_code",
        order_by="custom_item_code"
    )


@frappe.whitelist()
def get_batches_by_item_code(item_code, company=None, branch=None):
    """الحصول على الدفعات حسب كود الصنف"""
    filters = {"custom_item_code": item_code, "qty": [">", 0]}
    if company:
        filters["company"] = company
    if branch:
        filters["branch"] = branch

    return frappe.get_all(
        "Coffee Batch", filters=filters,
        fields=["name", "qty", "valuation_rate", "cost_per_kg", "total_value",
                "current_warehouse", "coffee_grade", "status"]
    )
