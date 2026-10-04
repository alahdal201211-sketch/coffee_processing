# -*- coding: utf-8 -*-

import frappe
from frappe import _
from frappe.utils import flt


# ============================================================
# Purchase Receipt -> Coffee Batch Automation
# ============================================================

DEFAULT_RECEIVING_COST_CENTER = "استلام البن - البن - ALC - بن1"

COFFEE_TYPE_ROUTE_MAP = {
    "Commercial": "مسار البن التجاري القياسي",
    "Specialty": "مسار البن المختص القياسي",
}


def on_purchase_receipt_submit(doc, method=None):
    """
    إنشاء Coffee Batch تلقائياً بعد Submit لـ Purchase Receipt.

    Purchase Receipt هو المسؤول عن حركة المخزون.
    هذه الخدمة تنشئ طبقة Coffee Batch والتتبع فقط.
    لا يتم إنشاء Stock Entry إضافي.
    """

    if not doc or doc.docstatus != 1:
        return

    for row in doc.items:

        if not row.item_code:
            continue

        item_data = frappe.db.get_value(
            "Item",
            row.item_code,
            [
                "item_name",
                "is_stock_item",
                "has_batch_no",
                "is_purchase_item",
            ],
            as_dict=True,
        )

        if not item_data:
            continue

        if not item_data.is_stock_item:
            continue

        if not item_data.has_batch_no:
            continue

        if not item_data.is_purchase_item:
            continue

        qty = flt(row.qty)

        if qty <= 0:
            continue

        batch_entries = _get_batch_entries(row)

        if not batch_entries:
            continue

        for entry in batch_entries:

            erpnext_batch = entry.get("batch_no")
            batch_qty = flt(entry.get("qty"))

            if not erpnext_batch or batch_qty <= 0:
                continue

            _ensure_coffee_batch(
                doc=doc,
                row=row,
                item_data=item_data,
                erpnext_batch=erpnext_batch,
                batch_qty=batch_qty,
            )


def _get_batch_entries(row):
    bundle_name = getattr(
        row,
        "serial_and_batch_bundle",
        None,
    )

    if not bundle_name:
        return []

    return frappe.get_all(
        "Serial and Batch Entry",
        filters={
            "parent": bundle_name,
            "parenttype": "Serial and Batch Bundle",
        },
        fields=[
            "batch_no",
            "qty",
        ],
        order_by="idx asc",
    )


def _ensure_coffee_batch(
    doc,
    row,
    item_data,
    erpnext_batch,
    batch_qty,
):
    existing = frappe.db.get_value(
        "Coffee Batch",
        {
            "purchase_receipt": doc.name,
            "custom_item_code": row.item_code,
            "supplier": doc.supplier,
            "company": doc.company,
            "erpnext_batch": erpnext_batch,
        },
        "name",
    )

    if existing:
        _ensure_purchase_source(
            existing,
            doc,
            row,
            erpnext_batch,
            batch_qty,
        )
        return existing

    branch = (
        getattr(doc, "branch", None)
        or getattr(row, "branch", None)
        or _get_company_branch(doc.company)
    )

    coffee_type = _get_coffee_type(row.item_code)

    route = _get_route(
        coffee_type=coffee_type,
        company=doc.company,
        branch=branch,
    )

    cost_center = _get_receiving_cost_center(
        row=row,
        doc=doc,
    )

    rate = flt(row.rate)

    if rate <= 0:
        rate = (
            flt(doc.get("grand_total"))
            / flt(doc.get("total_qty") or 1)
        )

    batch = frappe.new_doc("Coffee Batch")

    # Mandatory fields
    batch.custom_item_code = row.item_code
    batch.coffee_type = coffee_type
    batch.company = doc.company
    batch.source_type = "Purchase"
    batch.route = route
    batch.cost_center = cost_center

    # Optional / traceability fields
    batch.item_name = (
        item_data.item_name
        or row.item_code
    )

    if branch:
        batch.branch = branch

    batch.supplier = doc.supplier
    batch.purchase_receipt = doc.name

    batch.current_warehouse = row.warehouse

    batch.qty = batch_qty

    batch.valuation_rate = rate
    batch.cost_per_kg = rate
    batch.total_value = batch_qty * rate

    # ERPNext Batch link
    batch.erpnext_batch = erpnext_batch

    batch.status = "Received"

    batch.insert(ignore_permissions=True)

    _ensure_purchase_source(
        batch.name,
        doc,
        row,
        erpnext_batch,
        batch_qty,
    )

    return batch.name


def _get_coffee_type(item_code):
    meta = frappe.get_meta("Item")

    for fieldname in (
        "coffee_type",
        "custom_coffee_type",
    ):
        if meta.has_field(fieldname):
            value = frappe.db.get_value(
                "Item",
                item_code,
                fieldname,
            )

            if value:
                return value

    return "Commercial"


def _get_route(
    coffee_type,
    company,
    branch=None,
):
    route_name = COFFEE_TYPE_ROUTE_MAP.get(
        coffee_type,
        COFFEE_TYPE_ROUTE_MAP["Commercial"],
    )

    filters = {
        "name": route_name,
        "company": company,
        "active": 1,
    }

    if branch:
        filters["branch"] = branch

    route = frappe.db.get_value(
        "Coffee Process Route",
        filters,
        "name",
    )

    # If the route exists for company but branch differs,
    # use the active company route rather than failing.
    if not route:
        route = frappe.db.get_value(
            "Coffee Process Route",
            {
                "name": route_name,
                "company": company,
                "active": 1,
            },
            "name",
        )

    if not route:
        frappe.throw(
            _(
                "لم يتم العثور على مسار معالجة نشط لنوع البن {0}."
            ).format(coffee_type)
        )

    return route


def _get_receiving_cost_center(row, doc):
    cost_center = (
        getattr(row, "cost_center", None)
        or getattr(doc, "cost_center", None)
    )

    if cost_center:
        return cost_center

    exists = frappe.db.exists(
        "Cost Center",
        {
            "name": DEFAULT_RECEIVING_COST_CENTER,
            "company": doc.company,
            "is_group": 0,
        },
    )

    if exists:
        return DEFAULT_RECEIVING_COST_CENTER

    # Final company-level fallback
    cost_center = frappe.db.get_value(
        "Cost Center",
        {
            "company": doc.company,
            "is_group": 0,
        },
        "name",
    )

    if not cost_center:
        frappe.throw(
            _(
                "لا يوجد مركز تكلفة صالح للشركة {0}."
            ).format(doc.company)
        )

    return cost_center


def _get_company_branch(company):
    meta = frappe.get_meta("Company")

    if meta.has_field("branch"):
        return frappe.db.get_value(
            "Company",
            company,
            "branch",
        )

    return None


def _ensure_purchase_source(
    coffee_batch_name,
    doc,
    row,
    erpnext_batch,
    batch_qty,
):
    batch = frappe.get_doc(
        "Coffee Batch",
        coffee_batch_name,
    )

    for source in batch.get("purchase_sources") or []:

        if (
            source.purchase_receipt == doc.name
            and source.purchase_receipt_item == row.name
            and source.erpnext_batch == erpnext_batch
        ):
            return

    source = batch.append(
        "purchase_sources",
        {},
    )

    source.purchase_receipt = doc.name
    source.purchase_receipt_item = row.name

    purchase_invoice = _get_purchase_invoice(
        doc.name
    )

    if purchase_invoice:
        source.purchase_invoice = purchase_invoice

    source.supplier = doc.supplier
    source.item = row.item_code
    source.qty = batch_qty
    source.rate = flt(row.rate)

    source.amount = (
        flt(batch_qty) *
        flt(row.rate)
    )

    source.erpnext_batch = erpnext_batch

    batch.save(ignore_permissions=True)


def _get_purchase_invoice(purchase_receipt):
    result = frappe.db.sql(
        """
        SELECT parent
        FROM `tabPurchase Invoice Item`
        WHERE purchase_receipt = %s
          AND docstatus = 1
        ORDER BY creation DESC
        LIMIT 1
        """,
        (purchase_receipt,),
        as_dict=True,
    )

    return result[0].parent if result else None


def on_purchase_receipt_cancel(doc, method=None):
    """
    عند إلغاء Purchase Receipt يتم إلغاء Coffee Batch
    المرتبط به، بشرط ألا يكون قد دخل في معالجة لاحقة.
    """

    if not doc:
        return

    batches = frappe.get_all(
        "Coffee Batch",
        filters={
            "purchase_receipt": doc.name,
            "source_type": "Purchase",
        },
        fields=[
            "name",
            "qty",
            "status",
        ],
    )

    for batch_row in batches:

        batch = frappe.get_doc(
            "Coffee Batch",
            batch_row.name,
        )

        processed_statuses = {
            "In Process",
            "Graded",
            "Completed",
            "Sold",
            "Consumed",
        }

        if batch.status in processed_statuses:
            continue

        batch.status = "Rejected"
        batch.qty = 0
        batch.total_value = 0

        batch.save(ignore_permissions=True)


@frappe.whitelist()
def create_coffee_batches_from_purchase_receipt(
    purchase_receipt
):
    doc = frappe.get_doc(
        "Purchase Receipt",
        purchase_receipt,
    )

    if doc.docstatus != 1:
        frappe.throw(
            _("يجب أن يكون Purchase Receipt منشوراً.")
        )

    on_purchase_receipt_submit(doc)

    frappe.db.commit()

    return {
        "success": True,
        "purchase_receipt": doc.name,
    }
