# -*- coding: utf-8 -*-
"""Shared execution engine for stage-specific Coffee Processing documents.

The stage UI remains separate, while Coffee Process Order remains the central
stock/traceability engine. This keeps all processing movements consistent.
"""
import frappe
from frappe import _
from frappe.utils import flt, get_datetime

METHODS = ("Same Input Cost", "Quantity Based", "Relative Sales Value", "By-Product Credit", "Hybrid", "Manual")


def route_context(doc, operation_code):
    if not doc.inputs:
        frappe.throw(_("يجب إضافة دفعة إدخال واحدة على الأقل."))
    first = doc.inputs[0]
    batch = frappe.get_doc("Coffee Batch", first.coffee_batch)
    if not batch.route:
        frappe.throw(_("الدفعة {0} لا تحتوي على مسار معالجة.").format(batch.name))
    route = frappe.get_doc("Coffee Process Route", batch.route)

    if not route.active:
        frappe.throw(
            _("مسار المعالجة {0} غير نشط.").format(route.name)
        )

    # Multi-input operations must use batches from the same process route.
    # This prevents one Process Order from mixing batches that follow
    # different processing workflows.
    input_batches = []

    for row in (doc.inputs or []):
        if not row.coffee_batch:
            frappe.throw(_("دفعة البن مطلوبة لكل مدخل."))

        input_batch = frappe.get_doc(
            "Coffee Batch",
            row.coffee_batch,
        )

        if not input_batch.route:
            frappe.throw(
                _(
                    "الدفعة {0} لا تحتوي على مسار معالجة."
                ).format(input_batch.name)
            )

        if input_batch.route != route.name:
            frappe.throw(
                _(
                    "لا يمكن دمج الدفعة {0} مع بقية المدخلات لأن مسارها "
                    "{1} يختلف عن مسار الدفعة الأولى {2}."
                ).format(
                    input_batch.name,
                    input_batch.route,
                    route.name,
                )
            )

        input_batches.append(input_batch)

    steps = [s for s in route.steps if s.operation == operation_code or frappe.db.get_value("Coffee Operation Master", s.operation, "operation_code") == operation_code]
    if not steps:
        frappe.throw(_("العملية {0} غير موجودة في مسار الدفعة {1}.").format(operation_code, batch.route))
    step = sorted(steps, key=lambda x: x.sequence)[0]
    return batch, route, step


def validate_common(doc, operation_code, min_days=None, max_days=None):
    batch, route, step = route_context(doc, operation_code)
    operation = frappe.get_doc("Coffee Operation Master", operation_code)
    if doc.company and batch.company and doc.company != batch.company:
        frappe.throw(_("الدفعة لا تتبع الشركة المحددة."))
    if doc.branch and batch.branch and doc.branch != batch.branch:
        frappe.throw(_("الدفعة لا تتبع الفرع المحدد."))
    if not doc.inputs:
        frappe.throw(_("المدخلات مطلوبة."))
    if not doc.outputs:
        frappe.throw(_("المخرجات مطلوبة."))
    if not operation.allow_multiple_inputs and len(doc.inputs) != 1:
        frappe.throw(_("عملية {0} تسمح بمدخل واحد فقط.").format(operation.operation_name_ar))
    if not operation.allow_multiple_outputs and len(doc.outputs) != 1:
        frappe.throw(_("عملية {0} تسمح بمخرج واحد فقط.").format(operation.operation_name_ar))
    total_in = 0
    for r in doc.inputs:
        b = frappe.get_doc("Coffee Batch", r.coffee_batch)
        if flt(r.qty) <= 0: frappe.throw(_("كمية الإدخال يجب أن تكون أكبر من صفر."))
        if flt(r.qty) > flt(b.qty) + 0.000001: frappe.throw(_("الكمية تتجاوز المتاح في الدفعة {0}.").format(b.name))
        if not r.warehouse: r.warehouse = b.current_warehouse
        if r.warehouse != b.current_warehouse: frappe.throw(_("مخزن المدخل لا يطابق مخزن الدفعة {0}.").format(b.name))
        if not r.item: r.item = frappe.db.get_value("Batch", b.erpnext_batch, "item") or b.custom_item_code
        if not r.batch_no: r.batch_no = b.erpnext_batch
        r.rate = flt(r.rate or b.cost_per_kg or b.valuation_rate)
        r.amount = flt(r.qty) * r.rate
        total_in += flt(r.qty)
    total_out = sum(flt(r.qty) for r in doc.outputs)
    if total_out <= 0: frappe.throw(_("إجمالي المخرجات يجب أن يكون أكبر من صفر."))
    for r in doc.outputs:
        if flt(r.qty) <= 0: frappe.throw(_("كمية المخرج يجب أن تكون أكبر من صفر."))
        if not r.warehouse: r.warehouse = getattr(doc, "target_warehouse", None) or batch.current_warehouse
        if not r.item: frappe.throw(_("صنف المخرج مطلوب."))
        if not r.uom: r.uom = frappe.db.get_value("Item", r.item, "stock_uom") or "Kg"
        r.amount = flt(r.qty) * flt(r.rate or 0)
    doc.input_qty_total = total_in
    doc.output_qty_total = total_out
    doc.loss_qty = max(total_in-total_out, 0)
    doc.yield_percent = total_out/total_in*100 if total_in else 0
    if not doc.source_warehouse: doc.source_warehouse = batch.current_warehouse
    if not doc.target_warehouse: doc.target_warehouse = doc.outputs[0].warehouse
    if not doc.cost_allocation_method: doc.cost_allocation_method = "Same Input Cost"
    if doc.cost_allocation_method not in METHODS: frappe.throw(_("طريقة توزيع التكلفة غير صحيحة."))
    if min_days is not None or max_days is not None:
        if not doc.start_datetime or not doc.end_datetime:
            frappe.throw(_("بداية ونهاية العملية مطلوبة."))
        days = (get_datetime(doc.end_datetime)-get_datetime(doc.start_datetime)).total_seconds()/86400
        if min_days is not None and days < min_days: frappe.throw(_("مدة العملية أقل من الحد الأدنى: {0} يوم.").format(min_days))
        if max_days is not None and days > max_days: frappe.throw(_("مدة العملية أكبر من الحد الأقصى: {0} يوم.").format(max_days))
        doc.duration_hours = days*24
    direct = sum(flt(r.amount) for r in (doc.costs or []))
    doc.direct_cost = direct
    doc.total_cost = direct + flt(doc.overhead_cost)
    doc.cost_per_kg = doc.total_cost/total_out if total_out else 0
    return batch, route, step, operation


def create_process_order(doc, operation_code, min_days=None, max_days=None):
    batch, route, step, operation = validate_common(doc, operation_code, min_days, max_days)
    cpo = frappe.new_doc("Coffee Process Order")
    cpo.company = doc.company
    cpo.branch = doc.branch
    cpo.posting_date = doc.posting_date
    cpo.route = route.name
    cpo.route_step_sequence = step.sequence
    cpo.operation = operation_code
    cpo.operation_code = operation_code
    cpo.operation_name_ar = operation.operation_name_ar
    cpo.source_warehouse = doc.source_warehouse
    cpo.target_warehouse = doc.target_warehouse
    cpo.cost_center = getattr(doc, "cost_center", None) or operation.default_cost_center
    cpo.assigned_to = getattr(doc, "operator", None) or None
    cpo.required_role = operation.required_role
    cpo.weight_before = flt(doc.input_qty_total)
    cpo.weight_after = flt(doc.output_qty_total)
    cpo.quality_result = getattr(doc, "quality_result", None) or ("Approved" if operation.requires_quality else "Pending")
    cpo.sample_reference = getattr(doc, "sample_reference", None) or None
    cpo.approval_status = "Not Required" if not operation.requires_approval else getattr(doc, "approval_status", None) or "Pending"
    cpo.daily_monitoring_notes = getattr(doc, "drying_notes", None) or getattr(doc, "fermentation_notes", None) or getattr(doc, "remarks", None)
    cpo.cost_allocation_method = getattr(doc, "cost_allocation_method", None) or operation.cost_allocation_method
    cpo.variance_treatment_method = operation.variance_treatment_method
    cpo.process_cost_total = flt(doc.direct_cost)
    cpo.overhead_cost_total = flt(doc.overhead_cost)
    for r in doc.inputs:
        x=cpo.append("inputs",{})
        x.item=r.item; x.warehouse=r.warehouse; x.batch_no=r.batch_no; x.qty=r.qty; x.uom=r.uom; x.conversion_factor=1; x.valuation_rate=r.rate; x.amount=r.amount; x.coffee_batch=r.coffee_batch; x.source_voucher_type=doc.doctype; x.source_voucher_no=doc.name
    for r in doc.outputs:
        x=cpo.append("outputs",{})
        x.item=r.item; x.warehouse=r.warehouse; x.qty=r.qty; x.uom=r.uom; x.conversion_factor=1
        x.output_type = "By-Product" if getattr(r,'role',None)=='By-Product' else ("Main Product")
        x.is_saleable = 1 if x.output_type=="Main Product" else 0
        x.quality_status="Approved" if operation_code=="GRADING" else "Pending"; x.notes=getattr(r,'notes',None)
        x.valuation_rate=flt(r.rate or 0); x.amount=flt(r.amount or 0)
        if hasattr(x, "coffee_grade"): x.coffee_grade=getattr(r, "coffee_grade", None) or getattr(doc, "target_grade", None)
        if hasattr(x, "coffee_type"): x.coffee_type=getattr(batch, "coffee_type", None) or "Mixed"
    for r in (doc.costs or []):
        x=cpo.append("additional_costs",{}); x.expense_account=r.account; x.description=r.description; x.amount=flt(r.amount)
    cpo.insert(ignore_permissions=True)
    cpo.submit()
    doc.process_order=cpo.name
    doc.stock_entry=cpo.stock_entry
    doc.db_set("process_order",cpo.name,update_modified=False)
    doc.db_set("stock_entry",cpo.stock_entry,update_modified=False)
    return cpo


def allocate_resources(doc, storage_type, doctype, warehouse, capacity_default):
    """Allocate processing resources per input batch without mixing batches.

    Each physical resource is assigned to one Coffee Batch for this process
    order. This preserves batch traceability when an operation accepts multiple
    inputs (for example Sorting and Drying).
    """
    inputs = []

    for row in (doc.inputs or []):
        qty = flt(row.qty)
        if qty <= 0:
            continue

        if not row.coffee_batch:
            frappe.throw(_("دفعة البن مطلوبة لكل مدخل قبل تخصيص الموارد."))

        inputs.append(
            {
                "coffee_batch": row.coffee_batch,
                "qty": qty,
            }
        )

    if not inputs:
        return []

    filters = {
        "company": doc.company,
        "warehouse": warehouse,
        "active": 1,
        "status": ["in", ["متاح", "Available"]],
    }

    rows = frappe.get_all(
        doctype,
        filters=filters,
        fields=["name", "code", "capacity_kg", "warehouse"],
        order_by="code asc",
    )

    allocations = []
    resource_index = 0

    for item in inputs:
        remaining = item["qty"]

        while remaining > 0.000001:
            if resource_index >= len(rows):
                frappe.throw(
                    _(
                        "الطاقة الاستيعابية غير كافية للدفعة {0}. "
                        "المتبقي {1} كجم."
                    ).format(item["coffee_batch"], remaining)
                )

            resource = rows[resource_index]
            resource_index += 1

            cap = flt(resource.capacity_kg) or flt(capacity_default)

            if cap <= 0:
                continue

            take = min(cap, remaining)

            if take <= 0:
                continue

            unit = frappe.db.get_value(
                "Coffee Storage Unit",
                {"unit_code": resource.code},
                "name",
            )

            if not unit:
                su = frappe.get_doc(
                    {
                        "doctype": "Coffee Storage Unit",
                        "unit_code": resource.code,
                        "storage_type": storage_type,
                        "capacity_kg": cap,
                        "warehouse": warehouse,
                        "location": resource.code,
                        "company": doc.company,
                        "branch": doc.branch,
                        "status": "Occupied",
                        "active": 1,
                        "current_qty": take,
                    }
                )
                su.insert(ignore_permissions=True)
                unit = su.name
            else:
                current_qty = frappe.db.get_value(
                    "Coffee Storage Unit",
                    unit,
                    "current_qty",
                )

                if flt(current_qty) > 0:
                    frappe.throw(
                        _(
                            "وحدة التخزين {0} أصبحت مشغولة أثناء تخصيص الموارد."
                        ).format(resource.code)
                    )

                frappe.db.set_value(
                    "Coffee Storage Unit",
                    unit,
                    {
                        "storage_type": storage_type,
                        "capacity_kg": cap,
                        "warehouse": warehouse,
                        "location": resource.code,
                        "company": doc.company,
                        "branch": doc.branch,
                        "status": "Occupied",
                        "active": 1,
                        "current_qty": take,
                    },
                    update_modified=False,
                )

            doc.append(
                "resource_allocations",
                {
                    "storage_unit": unit,
                    "storage_type": storage_type,
                    "coffee_batch": item["coffee_batch"],
                    "allocated_qty": take,
                    "capacity_kg": cap,
                    "start_datetime": doc.start_datetime,
                    "end_datetime": doc.end_datetime,
                    "status": "Occupied",
                },
            )

            frappe.db.set_value(
                doctype,
                resource.name,
                {
                    "status": "مشغول",
                    "current_qty": take,
                    "current_process_order": doc.process_order,
                    "occupied_since": doc.start_datetime,
                },
                update_modified=False,
            )

            allocations.append(resource.name)
            remaining -= take

    return allocations


def release_resources(doc, doctype):
    for a in (doc.resource_allocations or []):
        unit=a.storage_unit
        if unit:
            frappe.db.set_value("Coffee Storage Unit",unit,{"status":"Available","current_qty":0,"current_process_order":None})
            code=frappe.db.get_value("Coffee Storage Unit",unit,"unit_code")
            if code:
                name=frappe.db.get_value(doctype,{"code":code},"name")
                if name: frappe.db.set_value(doctype,name,{"status":"متاح","current_qty":0,"current_process_order":None})
        a.status="Released"; a.end_datetime=doc.end_datetime
