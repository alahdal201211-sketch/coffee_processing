# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.utils import flt, now, nowdate, date_diff

from coffee_processing.coffee_processing.services.sequence_service import (
    get_next_executable_step,
    advance_batch_step,
    is_batch_completed,
)
from coffee_processing.coffee_processing.services.costing_service import (
    CostAllocationService,
)


def complete_processing(processing_order):
    """
    إكمال أمر المعالجة بعد اعتماده.

    التسلسل الصحيح:
    1. التحقق من أمر المعالجة.
    2. حساب الكميات الفعلية.
    3. التحقق من عدم تجاوز الكمية المتاحة.
    4. حساب الـ variance / loss / gain.
    5. توزيع التكلفة على المخرجات.
    6. إنشاء Coffee Batch مستقل لكل مخرج فعلي.
    7. تخفيض كمية الـ parent batch.
    8. تحديث حالة أمر المعالجة.
    """

    if isinstance(processing_order, str):
        order = frappe.get_doc(
            "Coffee Processing Order",
            processing_order,
        )
    else:
        order = processing_order

    if order.docstatus != 1:
        frappe.throw(
            _("Processing Order must be submitted first")
        )

    if not order.coffee_batch:
        frappe.throw(
            _("Coffee Batch is required")
        )

    if not order.operation:
        frappe.throw(
            _("Operation is required")
        )

    parent_batch = frappe.get_doc(
        "Coffee Batch",
        order.coffee_batch,
    )

    operation = frappe.get_doc(
        "Coffee Operation Master",
        order.operation,
    )

    # ---------------------------------------------------------
    # 1. قراءة الكميات الفعلية
    # ---------------------------------------------------------

    actual_input_qty = flt(
        sum(flt(i.actual_qty) for i in order.inputs)
    )

    actual_output_qty = flt(
        sum(
            flt(o.actual_qty)
            for o in order.outputs
            if o.output_type != "Loss"
        )
    )

    actual_loss_qty = flt(
        sum(
            flt(o.actual_qty)
            for o in order.outputs
            if o.output_type == "Loss"
        )
    )

    current_qty = flt(parent_batch.qty)

    if actual_input_qty <= 0:
        frappe.throw(
            _("Actual input quantity must be greater than zero")
        )

    # ---------------------------------------------------------
    # 2. التحقق من الكمية المتاحة
    # ---------------------------------------------------------

    if actual_input_qty > current_qty + 0.01:
        frappe.throw(
            _(
                "Insufficient quantity in batch {0}. "
                "Available: {1}, Requested: {2}"
            ).format(
                parent_batch.name,
                current_qty,
                actual_input_qty,
            )
        )

    # ---------------------------------------------------------
    # 3. حساب Variance
    #
    # Input = Output + Loss + Variance
    #
    # variance > 0  = shortage
    # variance < 0  = gain
    # variance = 0  = balanced
    # ---------------------------------------------------------

    variance_qty = flt(
        actual_input_qty
        - actual_output_qty
        - actual_loss_qty
    )

    # نسمح بهامش حساب بسيط جدًا بسبب الكسور العشرية
    if abs(variance_qty) < 0.0001:
        variance_qty = 0

    # إذا كانت العملية لا تسمح بالـ variance
    if variance_qty != 0 and not operation.allow_variance:
        frappe.throw(
            _(
                "Variance is not allowed for operation {0}. "
                "Input: {1}, Output: {2}, Loss: {3}, Variance: {4}"
            ).format(
                operation.operation_name_ar or operation.name,
                actual_input_qty,
                actual_output_qty,
                actual_loss_qty,
                variance_qty,
            )
        )

    # ---------------------------------------------------------
    # 4. تحديد الخطوة التالية قبل إنشاء الدفعات
    # ---------------------------------------------------------

    next_step = get_next_executable_step(parent_batch)

    # ---------------------------------------------------------
    # 5. توزيع التكلفة أولاً
    #
    # مهم جدًا:
    # لا ننشئ Output Batch قبل حساب output.rate
    # ---------------------------------------------------------

    CostAllocationService.allocate_costs(order)

    # إعادة تحميل الأمر لضمان الحصول على Rates التي
    # تم تثبيتها بواسطة CostAllocationService
    order.reload()

    results = {
        "parent_batch": parent_batch.name,
        "child_batches": [],
        "actual_input_qty": actual_input_qty,
        "actual_output_qty": actual_output_qty,
        "actual_loss_qty": actual_loss_qty,
        "variance_qty": variance_qty,
        "outputs": [],
    }

    # ---------------------------------------------------------
    # 6. إنشاء Batch مستقل لكل Output فعلي
    #
    # G14 = Batch مستقل
    # G16 = Batch مستقل
    # G17 = Batch مستقل
    # By-Product = Batch مستقل
    # Defect = Batch مستقل
    #
    # Loss لا ينشئ Batch.
    # ---------------------------------------------------------

    for output in order.outputs:

        output_qty = flt(output.actual_qty)

        # لا ننشئ Batch لمخرج صفر
        if output_qty <= 0:
            continue

        output_type = output.output_type or "Main"

        # Loss ليس Coffee Batch
        if output_type == "Loss":
            continue

        # -----------------------------------------------------
        # يجب أن تكون التكلفة محسوبة قبل إنشاء الـ Batch
        # -----------------------------------------------------

        output_rate = flt(output.rate)

        if output_rate <= 0:
            frappe.throw(
                _(
                    "Cost allocation did not produce a valid rate "
                    "for output {0}"
                ).format(
                    output.item_code or output.output_type or _("Output")
                )
            )

        child = _create_child_batch(
            parent_batch=parent_batch,
            output=output,
            order=order,
            next_step=next_step,
            operation=operation,
        )

        output.db_set(
            "batch",
            child.name,
        )

        output.db_set(
            "new_batch_no",
            child.name,
        )

        result_output = {
            "name": child.name,
            "custom_item_code": child.custom_item_code,
            "coffee_grade": child.coffee_grade,
            "coffee_type": child.coffee_type,
            "output_type": output_type,
            "qty": output_qty,
            "rate": output_rate,
            "amount": flt(output.amount),
        }

        results["child_batches"].append(result_output)
        results["outputs"].append(result_output)

    # ---------------------------------------------------------
    # 7. تحديث الكمية المتبقية في Parent Batch
    # ---------------------------------------------------------

    remaining_qty = flt(
        current_qty - actual_input_qty
    )

    if remaining_qty < 0 and abs(remaining_qty) < 0.01:
        remaining_qty = 0

    if remaining_qty > 0.01:

        parent_batch.db_set(
            "qty",
            remaining_qty,
        )

        # لا نمسح Reservation بشكل أعمى هنا.
        # سيتم إصلاح reservation logic في المرحلة التالية.

    else:

        parent_batch.db_set(
            "qty",
            0,
        )

        # الانتقال إلى الخطوة التالية
        advance_batch_step(
            parent_batch,
            order.operation,
        )

    # ---------------------------------------------------------
    # 8. تحديث حالة الـ Parent
    # ---------------------------------------------------------

    if operation.is_grading_operation:
        parent_batch.db_set(
            "status",
            "Graded",
        )

    parent_batch.reload()

    if is_batch_completed(parent_batch):
        parent_batch.db_set(
            "status",
            "Completed",
        )

    # ---------------------------------------------------------
    # 9. تحديث Processing Order
    # ---------------------------------------------------------

    order.db_set(
        "status",
        "Completed",
    )

    order.db_set(
        "actual_end_date",
        now(),
    )

    order.db_set(
        "completed_by",
        frappe.session.user,
    )

    order.db_set(
        "actual_qty",
        actual_input_qty,
    )

    # تثبيت النتائج على أمر المعالجة
    order.db_set(
        "total_input_qty",
        actual_input_qty,
    )

    order.db_set(
        "total_output_qty",
        actual_output_qty,
    )

    order.db_set(
        "total_loss_qty",
        actual_loss_qty,
    )

    order.db_set(
        "variance_qty",
        variance_qty,
    )

    if variance_qty > 0:
        order.db_set(
            "variance_type",
            "Shortage",
        )
    elif variance_qty < 0:
        order.db_set(
            "variance_type",
            "Gain",
        )
    else:
        order.db_set(
            "variance_type",
            "None",
        )

    frappe.db.commit()

    return results


def _create_child_batch(
    parent_batch,
    output,
    order,
    next_step,
    operation,
):
    """
    إنشاء Coffee Batch جديد للمخرج.

    كل Grade ينتج Batch مستقل:
        G14 -> Batch
        G16 -> Batch
        G17 -> Batch

    التكلفة تؤخذ من output.rate بعد Cost Allocation.
    """

    output_qty = flt(output.actual_qty)

    if output_qty <= 0:
        frappe.throw(
            _("Output quantity must be greater than zero")
        )

    output_rate = flt(output.rate)

    if output_rate <= 0:
        frappe.throw(
            _(
                "Output rate must be greater than zero "
                "before creating the batch"
            )
        )

    child = frappe.new_doc(
        "Coffee Batch"
    )

    # ---------------------------------------------------------
    # الهوية
    # ---------------------------------------------------------

    child.custom_item_code = (
        output.item_code
        or parent_batch.custom_item_code
    )

    child.item_name = (
        output.item_name
        or output.item_code
        or parent_batch.item_name
        or parent_batch.custom_item_code
    )

    child.coffee_type = (
        output.coffee_type
        or parent_batch.coffee_type
    )

    child.coffee_grade = output.coffee_grade

    child.is_grade_batch = (
        1 if output.coffee_grade else 0
    )

    # ---------------------------------------------------------
    # المصدر
    # ---------------------------------------------------------

    if operation.is_grading_operation:
        child.source_type = "Grading"
    else:
        child.source_type = "Processing"

    child.parent_batch = parent_batch.name
    child.route = parent_batch.route

    # ---------------------------------------------------------
    # الخطوة التالية
    # ---------------------------------------------------------

    if next_step:
        child.current_step = next_step.sequence
        child.current_operation = next_step.operation
    else:
        child.current_step = parent_batch.current_step
        child.current_operation = parent_batch.current_operation

    child.status = "Ready for Processing"

    # ---------------------------------------------------------
    # الشركة / الفرع / المستودع / التكلفة
    # ---------------------------------------------------------

    child.current_warehouse = (
        output.warehouse
        or parent_batch.current_warehouse
    )

    child.cost_center = (
        output.cost_center
        or parent_batch.cost_center
    )

    child.company = parent_batch.company
    child.branch = parent_batch.branch

    # ---------------------------------------------------------
    # Quality / Cupping
    # ---------------------------------------------------------

    child.quality_status = (
        parent_batch.quality_status
    )

    child.cupping_status = (
        parent_batch.cupping_status
    )

    # ---------------------------------------------------------
    # الكمية والتكلفة
    #
    # أهم نقطة:
    # valuation_rate = output.rate
    # وليس parent_batch.valuation_rate
    # ---------------------------------------------------------

    child.qty = output_qty

    child.valuation_rate = output_rate

    child.total_value = flt(
        output_qty * output_rate
    )

    child.cost_per_kg = output_rate

    # ---------------------------------------------------------
    # الحفظ
    # ---------------------------------------------------------

    child.insert(
        ignore_permissions=True
    )

    return child


def get_processing_summary(batch_name):
    batch = frappe.get_doc(
        "Coffee Batch",
        batch_name,
    )

    orders = frappe.get_all(
        "Coffee Processing Order",
        filters={
            "coffee_batch": batch_name,
            "docstatus": 1,
        },
        fields=[
            "name",
            "operation",
            "actual_qty",
            "status",
            "creation",
        ],
        order_by="creation asc",
    )

    child_batches = frappe.get_all(
        "Coffee Batch",
        filters={
            "parent_batch": batch_name,
        },
        fields=[
            "name",
            "custom_item_code",
            "coffee_grade",
            "coffee_type",
            "qty",
            "cost_per_kg",
            "valuation_rate",
            "total_value",
            "status",
            "is_grade_batch",
        ],
    )

    return {
        "batch": batch.name,
        "orders": orders,
        "child_batches": child_batches,
        "total_processed": sum(
            flt(o.actual_qty)
            for o in orders
        ),
        "current_step": batch.current_step,
        "current_operation": batch.current_operation,
        "is_completed": is_batch_completed(batch),
        "grade_batches": [
            cb
            for cb in child_batches
            if cb.is_grade_batch
        ],
    }


def check_open_processing_orders():
    orders = frappe.get_all(
        "Coffee Processing Order",
        filters={
            "docstatus": 1,
            "status": ["in", ["Approved", "In Progress"]],
        },
        fields=[
            "name",
            "order_no",
            "planned_end_date",
            "coffee_batch",
        ],
    )

    for o in orders:

        if not o.planned_end_date:
            continue

        if date_diff(
            nowdate(),
            o.planned_end_date,
        ) > 0:

            frappe.publish_realtime(
                event="coffee_processing_overdue",
                message={
                    "order": o.name,
                    "batch": o.coffee_batch,
                },
            )
