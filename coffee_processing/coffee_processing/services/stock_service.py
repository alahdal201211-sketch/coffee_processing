# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import flt


def get_batch_qty(batch_name):
    """الحصول على الكمية الحالية من Coffee Batch مباشرة"""
    if not batch_name:
        return 0
    qty = frappe.db.get_value("Coffee Batch", batch_name, "qty")
    return flt(qty) or 0


def get_batch_value(batch_name):
    """الحصول على القيمة الإجمالية"""
    if not batch_name:
        return 0
    batch = frappe.db.get_value("Coffee Batch", batch_name,
                                 ["qty", "valuation_rate"], as_dict=True)
    if not batch:
        return 0
    return flt(batch.qty) * flt(batch.valuation_rate)


def get_batch_available_qty(batch_name):
    """الكمية المتاحة = qty - reserved_qty"""
    if not batch_name:
        return 0
    batch = frappe.db.get_value("Coffee Batch", batch_name,
                                 ["qty", "reserved_qty"], as_dict=True)
    if not batch:
        return 0
    return flt(batch.qty) - flt(batch.reserved_qty)


def get_batch_cost_per_kg(batch_name):
    """التكلفة لكل كجم"""
    if not batch_name:
        return 0
    return flt(frappe.db.get_value("Coffee Batch", batch_name, "cost_per_kg"))


def update_batch_qty(batch_name, qty, rate=None):
    """تحديث كمية الدفعة مع حساب المتوسط المرجح"""
    batch = frappe.get_doc("Coffee Batch", batch_name)
    if qty > 0:
        batch.add_qty(qty, rate)
    else:
        batch.reduce_qty(abs(qty))
    batch.save(ignore_permissions=True)
    return batch


def get_available_batches(coffee_type=None, coffee_grade=None,
                          company=None, branch=None, is_grade_batch=None,
                          warehouse=None, status=None):
    """الحصول على الدفعات المتاحة"""
    filters = {}
    if coffee_type:
        filters["coffee_type"] = coffee_type
    if coffee_grade:
        filters["coffee_grade"] = coffee_grade
    if company:
        filters["company"] = company
    if branch:
        filters["branch"] = branch
    if is_grade_batch is not None:
        filters["is_grade_batch"] = is_grade_batch
    if warehouse:
        filters["current_warehouse"] = warehouse
    if status:
        filters["status"] = status
    else:
        filters["status"] = ["in", ["Received", "Ready for Processing", "In Process", "Graded"]]

    return frappe.get_all(
        "Coffee Batch", filters=filters,
        fields=["name", "custom_item_code", "item_name", "coffee_type",
                "coffee_grade", "qty", "valuation_rate", "cost_per_kg",
                "total_value", "reserved_qty", "current_warehouse",
                "company", "branch", "is_grade_batch", "status"],
        order_by="creation desc"
    )


def create_stock_entry_for_processing(order):
    """
    اختياري: إنشاء Stock Entry عند الحاجة الفعلية
    (مثلاً: تحويل بين الفروع، أو عند استخدام ERPNext Inventory)
    """
    # يمكن تفعيلها إذا كنت تستخدم ERPNext Inventory
    return None


def reduce_batch_qty(batch_name, qty):
    """تقليل كمية الدفعة (عند البيع مثلاً)"""
    batch = frappe.get_doc("Coffee Batch", batch_name)
    batch.reduce_qty(qty)
    batch.save(ignore_permissions=True)
    return batch


def _get_or_create_erpnext_batch(item, company, posting_date, batch_no=None):
    """Return an ERPNext Batch for a stock output."""
    if batch_no and frappe.db.exists("Batch", batch_no):
        return batch_no

    batch = frappe.new_doc("Batch")
    batch.item = item

    if batch_no:
        batch.name = batch_no

    batch.batch_id = batch_no or None
    batch.manufacturing_date = posting_date
    batch.insert(ignore_permissions=True)

    return batch.name


def create_repack_stock_entry(
    company,
    posting_date,
    inputs,
    outputs,
    title="Coffee Processing Repack",
):
    """
    Create an ERPNext Repack Stock Entry.

    inputs:
        [
            {
                "item": str,
                "qty": float,
                "uom": str,
                "warehouse": str,
                "batch_no": str | None,
                "rate": float,
            }
        ]

    outputs:
        [
            {
                "item": str,
                "qty": float,
                "uom": str,
                "warehouse": str,
                "batch_no": str | None,
                "rate": float,
            }
        ]

    Returns:
        (stock_entry_doc, output_rows)
    """

    if not company:
        frappe.throw(_("Company is required."))

    if not inputs:
        frappe.throw(_("At least one stock input is required."))

    if not outputs:
        frappe.throw(_("At least one stock output is required."))

    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Repack"
    se.company = company
    se.posting_date = posting_date
    se.purpose = "Repack"
    se.title = title

    # Inputs
    for row in inputs:
        qty = flt(row.get("qty"))

        if qty <= 0:
            continue

        item = row.get("item")
        warehouse = row.get("warehouse")

        if not item:
            frappe.throw(_("Input item is required."))

        if not warehouse:
            frappe.throw(
                _("Warehouse is required for input item {0}.").format(item)
            )

        child = se.append("items", {})
        child.item_code = item
        child.s_warehouse = warehouse
        child.qty = qty
        child.uom = row.get("uom") or frappe.db.get_value(
            "Item", item, "stock_uom"
        )
        child.conversion_factor = 1
        child.basic_rate = flt(row.get("rate"))

        batch_no = row.get("batch_no")
        if batch_no:
            child.batch_no = batch_no

    # Outputs
    output_rows = []

    for row in outputs:
        qty = flt(row.get("qty"))

        if qty <= 0:
            continue

        item = row.get("item")
        warehouse = row.get("warehouse")

        if not item:
            frappe.throw(_("Output item is required."))

        if not warehouse:
            frappe.throw(
                _("Warehouse is required for output item {0}.").format(item)
            )

        child = se.append("items", {})
        child.item_code = item
        child.t_warehouse = warehouse
        child.qty = qty
        child.uom = row.get("uom") or frappe.db.get_value(
            "Item", item, "stock_uom"
        )
        child.conversion_factor = 1
        child.basic_rate = flt(row.get("rate"))

        batch_no = row.get("batch_no")

        if batch_no:
            child.batch_no = batch_no

        output_rows.append((row, child))

    if not se.items:
        frappe.throw(_("No valid stock rows were provided."))

    se.insert(ignore_permissions=True)
    se.submit()

    return se, output_rows
