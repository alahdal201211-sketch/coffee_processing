import frappe
from frappe import _
from frappe.utils import flt


OPERATION_MAP = {
    "Coffee Receiving Order": {
        "code": "REC",
        "name": "RECEIVING",
        "label": "الاستلام",
    },
    "Coffee Sorting Order": {
        "code": "SORT",
        "name": "SORTING",
        "label": "الفرز",
    },
    "Coffee Fermentation Order": {
        "code": "FER",
        "name": "FERMENTATION",
        "label": "التخمير",
    },
    "Coffee Drying Order": {
        "code": "DRY",
        "name": "DRYING",
        "label": "التجفيف",
    },
    "Coffee Peeling Service": {
        "code": "HUL",
        "name": "HULLING",
        "label": "التقشير",
    },
    "Coffee Grading Order": {
        "code": "GRD",
        "name": "GRADING",
        "label": "التصنيف",
    },
    "Coffee Cupping": {
        "code": "CUP",
        "name": "CUPPING",
        "label": "التذوق",
    },
    "Coffee Packaging Order": {
        "code": "PKG",
        "name": "PACKAGING",
        "label": "التعبئة",
    },
    "Coffee Blend Order": {
        "code": "BLN",
        "name": "BLENDING",
        "label": "الخلط",
    },
}


def get_operation_info(doctype):
    return OPERATION_MAP.get(doctype, {})


def get_operation_code(doctype):
    return get_operation_info(doctype).get("code")


def validate_batch(batch_name, company=None):
    if not batch_name:
        frappe.throw(_("دفعة البن مطلوبة."))

    if not frappe.db.exists("Coffee Batch", batch_name):
        frappe.throw(
            _("دفعة البن غير موجودة: {0}").format(batch_name)
        )

    batch = frappe.get_doc("Coffee Batch", batch_name)

    if company and batch.company and batch.company != company:
        frappe.throw(
            _("الشركة في الدفعة لا تطابق الشركة في أمر العملية.")
        )

    if flt(batch.qty) < 0:
        frappe.throw(
            _("لا يمكن أن تكون كمية الدفعة سالبة.")
        )

    return batch


def validate_operation_batches(doc):
    """
    التحقق المشترك من دفعات الإدخال والإخراج.
    لا يقوم بأي حركة مخزون.
    """

    if not getattr(doc, "inputs", None):
        frappe.throw(
            _("يجب إضافة دفعة إدخال واحدة على الأقل.")
        )

    input_total = 0

    for row in doc.inputs:
        if not row.coffee_batch:
            frappe.throw(
                _("يجب تحديد دفعة البن في جميع صفوف الإدخال.")
            )

        qty = flt(row.qty)

        if qty <= 0:
            frappe.throw(
                _("كمية الإدخال يجب أن تكون أكبر من صفر.")
            )

        validate_batch(
            row.coffee_batch,
            getattr(doc, "company", None)
        )

        input_total += qty

    output_total = 0

    for row in getattr(doc, "outputs", None) or []:
        if not row.coffee_batch:
            continue

        qty = flt(row.qty)

        if qty <= 0:
            frappe.throw(
                _("كمية الإخراج يجب أن تكون أكبر من صفر.")
            )

        validate_batch(
            row.coffee_batch,
            getattr(doc, "company", None)
        )

        output_total += qty

    if hasattr(doc, "input_qty_total"):
        doc.input_qty_total = input_total

    if hasattr(doc, "output_qty_total"):
        doc.output_qty_total = output_total

    if hasattr(doc, "loss_qty"):
        doc.loss_qty = max(input_total - output_total, 0)

    if hasattr(doc, "yield_percent"):
        doc.yield_percent = (
            output_total / input_total * 100
            if input_total else 0
        )

    return {
        "input_qty": input_total,
        "output_qty": output_total,
        "loss_qty": max(input_total - output_total, 0),
        "yield_percent": (
            output_total / input_total * 100
            if input_total else 0
        ),
    }


def calculate_operation_cost(doc):
    direct = 0

    for row in getattr(doc, "costs", None) or []:
        qty = flt(row.qty)
        rate = flt(row.rate)

        if flt(row.amount) == 0 and qty and rate:
            row.amount = qty * rate

        direct += flt(row.amount)

    overhead = flt(
        getattr(doc, "overhead_cost", 0)
    )

    total = direct + overhead

    if hasattr(doc, "direct_cost"):
        doc.direct_cost = direct

    if hasattr(doc, "total_cost"):
        doc.total_cost = total

    output_qty = flt(
        getattr(doc, "output_qty_total", 0)
    )

    if hasattr(doc, "cost_per_kg"):
        doc.cost_per_kg = (
            total / output_qty
            if output_qty else 0
        )

    return {
        "direct_cost": direct,
        "overhead_cost": overhead,
        "total_cost": total,
        "cost_per_kg": (
            total / output_qty
            if output_qty else 0
        ),
    }


def get_batch_trace(batch_name):
    """
    قراءة سلسلة التتبع المرتبطة بالدفعة.
    لا تعدل أي بيانات.
    """

    if not frappe.db.exists("Coffee Batch", batch_name):
        frappe.throw(
            _("دفعة البن غير موجودة: {0}").format(batch_name)
        )

    batch = frappe.get_doc("Coffee Batch", batch_name)

    result = {
        "batch": batch.name,
        "item": batch.custom_item_code,
        "qty": flt(batch.qty),
        "parent_batch": batch.parent_batch,
        "split_from": batch.split_from,
        "merged_into": batch.merged_into,
        "source_type": batch.source_type,
        "supplier": batch.supplier,
        "purchase_receipt": batch.purchase_receipt,
        "operations": [],
    }

    # Coffee Process Orders
    process_orders = frappe.get_all(
        "Coffee Process Order",
        filters=[
            ["Coffee Process Order Input",
             "coffee_batch", "=", batch_name]
        ],
        fields=[
            "name",
            "posting_date",
            "operation",
            "status"
        ],
        distinct=True
    )

    for row in process_orders:
        result["operations"].append({
            "doctype": "Coffee Process Order",
            "name": row.name,
            "operation": row.operation,
            "posting_date": row.posting_date,
            "status": row.status,
        })

    return result


def get_operation_summary(doc):
    info = get_operation_info(doc.doctype)

    return {
        "doctype": doc.doctype,
        "operation_code": info.get("code"),
        "operation_name": info.get("name"),
        "operation_label": info.get("label"),
        "name": doc.name,
        "status": doc.status,
        "input_qty": flt(
            getattr(doc, "input_qty_total", 0)
        ),
        "output_qty": flt(
            getattr(doc, "output_qty_total", 0)
        ),
        "loss_qty": flt(
            getattr(doc, "loss_qty", 0)
        ),
        "yield_percent": flt(
            getattr(doc, "yield_percent", 0)
        ),
        "total_cost": flt(
            getattr(doc, "total_cost", 0)
        ),
        "cost_per_kg": flt(
            getattr(doc, "cost_per_kg", 0)
        ),
    }


@frappe.whitelist()
def get_trace(batch_name):
    return get_batch_trace(batch_name)


@frappe.whitelist()
def get_summary(doctype, name):
    if not frappe.db.exists(doctype, name):
        frappe.throw(
            _("المستند غير موجود.")
        )

    return get_operation_summary(
        frappe.get_doc(doctype, name)
    )
