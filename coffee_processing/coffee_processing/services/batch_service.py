# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, nowdate, date_diff


def update_all_batch_qty():
    """تحديث كل الدفعات (مهمة يومية)"""
    batches = frappe.get_all(
        "Coffee Batch",
        filters={"status": ["in", ["Received", "Ready for Processing", "In Process", "Graded"]]},
        pluck="name"
    )
    for batch_name in batches:
        try:
            batch = frappe.get_doc("Coffee Batch", batch_name)
            batch.calculate_totals()
            batch.save(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Batch update failed for {batch_name}: {str(e)}",
                             "Coffee Batch Update")


def check_batch_deadlines():
    batches = frappe.get_all(
        "Coffee Batch",
        filters={"status": ["in", ["In Process", "Ready for Processing"]]},
        fields=["name", "route", "current_step", "creation"]
    )
    for batch_data in batches:
        try:
            batch = frappe.get_doc("Coffee Batch", batch_data.name)
            if not batch.route or not batch.current_step:
                continue
            route = frappe.get_doc("Coffee Process Route", batch.route)
            current_step = next((s for s in route.steps if s.sequence == batch.current_step), None)
            if not current_step or not current_step.maximum_days:
                continue
            days_in_step = date_diff(nowdate(), batch_data.creation)
            if days_in_step > current_step.maximum_days:
                frappe.publish_realtime(
                    event="coffee_batch_overdue",
                    message={"batch": batch.name, "days": days_in_step,
                             "max_days": current_step.maximum_days}
                )
        except Exception as e:
            frappe.log_error(f"Deadline check failed for {batch_data.name}: {str(e)}",
                             "Coffee Batch Deadline")


def split_batch(batch_name, split_qty, new_warehouse=None):
    batch = frappe.get_doc("Coffee Batch", batch_name)
    if split_qty <= 0:
        frappe.throw(_("Cannot split batch with zero quantity"))
    if split_qty >= flt(batch.qty):
        frappe.throw(_("Cannot split quantity must be less than batch quantity"))

    new_batch = frappe.new_doc("Coffee Batch")
    new_batch.custom_item_code = batch.custom_item_code
    new_batch.item_name = batch.item_name
    new_batch.coffee_type = batch.coffee_type
    new_batch.coffee_grade = batch.coffee_grade
    new_batch.is_grade_batch = batch.is_grade_batch
    new_batch.source_type = "Split"
    new_batch.split_from = batch.name
    new_batch.parent_batch = batch.name
    new_batch.route = batch.route
    new_batch.current_step = batch.current_step
    new_batch.current_operation = batch.current_operation
    new_batch.status = batch.status
    new_batch.current_warehouse = new_warehouse or batch.current_warehouse
    new_batch.cost_center = batch.cost_center
    new_batch.quality_status = batch.quality_status
    new_batch.cupping_status = batch.cupping_status
    new_batch.company = batch.company
    new_batch.branch = batch.branch
    new_batch.qty = split_qty
    new_batch.valuation_rate = batch.valuation_rate
    new_batch.insert(ignore_permissions=True)

    # تقليل الكمية من الدفعة الأم
    batch.reduce_qty(split_qty)
    batch.save(ignore_permissions=True)

    return new_batch


def merge_batches(batch_names, target_warehouse=None):
    """دمج دفعات - لا يسمح بدمج درجات مختلفة"""
    if len(batch_names) < 2:
        frappe.throw(_("At least two batches are required"))

    batches = [frappe.get_doc("Coffee Batch", name) for name in batch_names]

    # التحقق: لا دمج درجات مختلفة
    grades = set(b.coffee_grade for b in batches if b.coffee_grade)
    if len(grades) > 1:
        frappe.throw(_("Cannot merge batches with different grades. Use Blend Order instead."))

    total_qty = sum(flt(b.qty) for b in batches)
    if total_qty <= 0:
        frappe.throw(_("Cannot merge batches with zero total quantity"))

    # حساب المتوسط المرجح للسعر
    total_value = sum(flt(b.qty) * flt(b.valuation_rate or 0) for b in batches)
    avg_rate = total_value / total_qty if total_qty > 0 else 0

    merged = frappe.new_doc("Coffee Batch")
    merged.custom_item_code = batches[0].custom_item_code
    merged.item_name = batches[0].item_name
    merged.coffee_type = batches[0].coffee_type
    merged.coffee_grade = batches[0].coffee_grade
    merged.is_grade_batch = batches[0].is_grade_batch
    merged.source_type = "Merge"
    merged.parent_batch = batches[0].name
    merged.route = batches[0].route
    merged.current_step = batches[0].current_step
    merged.current_operation = batches[0].current_operation
    merged.status = "Ready for Processing"
    merged.current_warehouse = target_warehouse or batches[0].current_warehouse
    merged.cost_center = batches[0].cost_center
    merged.company = batches[0].company
    merged.branch = batches[0].branch
    merged.qty = total_qty
    merged.valuation_rate = avg_rate
    merged.insert(ignore_permissions=True)

    for b in batches:
        b.db_set("merged_into", merged.name)
        b.db_set("status", "Consumed")
        b.db_set("qty", 0)

    return merged
