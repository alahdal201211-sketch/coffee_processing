import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


SORTING_OPERATION_CODE = "SORTING"


class CoffeeSortingOrder(Document):
    """
    Coffee Sorting Order
    --------------------
    واجهة تشغيل لعملية الفرز فوق المحرك المركزي Coffee Process Order.

    التصميم:
        Coffee Sorting Order
                ↓
        Coffee Process Order
                ↓
        ERPNext Stock Entry (Repack)
                ↓
        Coffee Batch / ERPNext Batch

    لا يتم إنشاء Stock Entry مباشرة هنا.
    """

    def validate(self):
        self._validate_header()
        self._load_sorting_operation()
        self._load_route_context()
        self._validate_inputs()
        self._prepare_input_rows()
        self._prepare_output_rows()
        self._calculate_totals()
        self._validate_quantities()
        self._calculate_costs()
        self._validate_manual_costs()

    # ------------------------------------------------------------------
    # Header / Master Data
    # ------------------------------------------------------------------

    def _validate_header(self):
        if not self.company:
            frappe.throw(_("يجب تحديد الشركة."))

        if not self.branch:
            frappe.throw(_("يجب تحديد الفرع."))

        if not self.posting_date:
            frappe.throw(_("يجب تحديد تاريخ العملية."))

        if not self.sorting_method:
            frappe.throw(_("يجب تحديد طريقة الفرز."))

    def _load_sorting_operation(self):
        filters = {
            "operation_code": SORTING_OPERATION_CODE,
            "active": 1,
            "company": self.company,
        }

        if self.branch:
            filters["branch"] = self.branch

        operation_name = frappe.db.get_value(
            "Coffee Operation Master",
            filters,
            "name",
            order_by="modified desc",
        )

        if not operation_name:
            frappe.throw(
                _(
                    "لا توجد عملية SORTING نشطة للشركة {0} والفرع {1}."
                ).format(self.company, self.branch)
            )

        operation = frappe.get_doc(
            "Coffee Operation Master",
            operation_name,
        )

        if operation.operation_code != SORTING_OPERATION_CODE:
            frappe.throw(_("إعداد عملية الفرز غير صحيح."))

        self._sorting_operation = operation

        if hasattr(operation, "allow_multiple_inputs") and operation.allow_multiple_inputs:
            pass

        if hasattr(operation, "allow_multiple_outputs") and not operation.allow_multiple_outputs:
            if len(self.outputs or []) > 1:
                frappe.throw(_("عملية الفرز لا تسمح بأكثر من مخرج واحد حسب الإعدادات."))

    # ------------------------------------------------------------------
    # Route
    # ------------------------------------------------------------------

    def _load_route_context(self):
        if not self.inputs:
            return

        first_row = self.inputs[0]

        if not first_row.coffee_batch:
            return

        batch = frappe.get_doc(
            "Coffee Batch",
            first_row.coffee_batch,
        )

        self._input_batch = batch

        route_name = batch.route

        if not route_name:
            frappe.throw(
                _(
                    "الدفعة {0} لا تحتوي على مسار معالجة."
                ).format(batch.name)
            )

        route = frappe.get_doc(
            "Coffee Process Route",
            route_name,
        )

        if not route.active:
            frappe.throw(
                _("مسار المعالجة {0} غير نشط.").format(route.name)
            )

        if route.company and route.company != self.company:
            frappe.throw(
                _(
                    "مسار المعالجة {0} لا يتبع الشركة {1}."
                ).format(route.name, self.company)
            )

        if route.branch and route.branch != self.branch:
            frappe.throw(
                _(
                    "مسار المعالجة {0} لا يتبع الفرع {1}."
                ).format(route.name, self.branch)
            )

        # جميع مدخلات الفرز يجب أن تتبع نفس مسار المعالجة.
        # Sorting يسمح بأكثر من مدخل، لذلك لا يكفي فحص الدفعة الأولى فقط.
        for row in self.inputs:
            if not row.coffee_batch:
                frappe.throw(
                    _("يجب تحديد Coffee Batch لكل مدخل.")
                )

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
                        route.name
                    )
                )

        sorting_steps = [
            step
            for step in route.steps
            if step.operation == self._sorting_operation.name
            or frappe.db.get_value(
                "Coffee Operation Master",
                step.operation,
                "operation_code",
            )
            == SORTING_OPERATION_CODE
        ]

        if not sorting_steps:
            frappe.throw(
                _(
                    "العملية SORTING غير موجودة في مسار المعالجة {0}."
                ).format(route.name)
            )

        sorting_step = sorted(
            sorting_steps,
            key=lambda x: x.sequence,
        )[0]

        self._route = route
        self._sorting_step = sorting_step
        self._route_sequence = sorting_step.sequence

        self.route = route.name
        self.operation_no = str(sorting_step.sequence)

        # لا يوجد route field في Sorting Order JSON، لذلك نخزن
        # المسار في Process Order فقط عند إنشائه.
        self._next_route_step = self._get_next_route_step(
            route,
            sorting_step,
        )

    def _get_next_route_step(self, route, current_step):
        steps = sorted(
            route.steps,
            key=lambda x: x.sequence,
        )

        for step in steps:
            if step.sequence <= current_step.sequence:
                continue

            if step.required:
                return step

            if not step.allow_skip_if_optional:
                return step

        return None

    # ------------------------------------------------------------------
    # Input Validation
    # ------------------------------------------------------------------

    def _validate_inputs(self):
        if not self.inputs:
            frappe.throw(
                _("يجب إضافة دفعة إدخال واحدة على الأقل.")
            )

        if len(self.inputs) != 1:
            if not getattr(
                self._sorting_operation,
                "allow_multiple_inputs",
                0,
            ):
                frappe.throw(
                    _("عملية الفرز الحالية تسمح بدفعة إدخال واحدة فقط.")
                )

        for row in self.inputs:
            if not row.coffee_batch:
                frappe.throw(
                    _("يجب تحديد Coffee Batch لكل مدخل.")
                )

            if flt(row.qty) <= 0:
                frappe.throw(
                    _("كمية الإدخال يجب أن تكون أكبر من صفر.")
                )

            if not frappe.db.exists(
                "Coffee Batch",
                row.coffee_batch,
            ):
                frappe.throw(
                    _("دفعة البن {0} غير موجودة.").format(
                        row.coffee_batch
                    )
                )

    def _prepare_input_rows(self):
        for row in self.inputs:
            batch = frappe.get_doc(
                "Coffee Batch",
                row.coffee_batch,
            )

            if not self._input_batch:
                self._input_batch = batch

            if batch.company and batch.company != self.company:
                frappe.throw(
                    _(
                        "الدفعة {0} لا تتبع الشركة المحددة."
                    ).format(batch.name)
                )

            if batch.branch and batch.branch != self.branch:
                frappe.throw(
                    _(
                        "الدفعة {0} لا تتبع الفرع المحدد."
                    ).format(batch.name)
                )

            if batch.qty <= 0:
                frappe.throw(
                    _("الدفعة {0} لا تحتوي على كمية متاحة.").format(
                        batch.name
                    )
                )

            if batch.status not in (
                "Ready for Processing",
                "In Process",
            ):
                frappe.throw(
                    _(
                        "الدفعة {0} ليست جاهزة للفرز. الحالة الحالية: {1}"
                    ).format(batch.name, batch.status)
                )

            if not batch.current_warehouse:
                frappe.throw(
                    _(
                        "الدفعة {0} لا تحتوي على مستودع حالي."
                    ).format(batch.name)
                )

            if flt(row.qty) > flt(batch.qty):
                frappe.throw(
                    _(
                        "كمية الإدخال {0} تتجاوز الكمية المتاحة للدفعة {1} وهي {2}."
                    ).format(
                        flt(row.qty),
                        batch.name,
                        flt(batch.qty),
                    )
                )

            row.item = batch.custom_item_code or batch.item
            row.batch_no = batch.erpnext_batch
            row.warehouse = batch.current_warehouse
            row.rate = flt(
                batch.valuation_rate
                or batch.cost_per_kg
                or 0
            )
            row.amount = flt(row.qty) * flt(row.rate)

    # ------------------------------------------------------------------
    # Output Validation
    # ------------------------------------------------------------------

    def _prepare_output_rows(self):
        if not self.outputs:
            frappe.throw(
                _("يجب إضافة مخرج واحد على الأقل لعملية الفرز.")
            )

        for row in self.outputs:
            if flt(row.qty) <= 0:
                frappe.throw(
                    _("كمية المخرج يجب أن تكون أكبر من صفر.")
                )

            if row.role not in (
                "Output",
                "Reject",
                "By-Product",
            ):
                frappe.throw(
                    _(
                        "نوع الدور في مخرجات الفرز غير صحيح: {0}"
                    ).format(row.role)
                )

            # الناتج يذهب إلى نفس مستودع العملية ما لم يتم تحديده صراحة.
            if not row.warehouse:
                row.warehouse = (
                    self._input_batch.current_warehouse
                    if self._input_batch
                    else None
                )

            if not row.warehouse:
                frappe.throw(
                    _("يجب تحديد مستودع المخرج.")
                )

            if not row.item:
                frappe.throw(
                    _("تعذر تحديد صنف ERPNext الحقيقي لمخرج الفرز.")
                )

            if row.role == "Output":
                row.notes = row.notes or self.reject_reason or ""
            elif row.role == "Reject":
                row.notes = row.notes or self.reject_reason or "فرز - مرفوض"
            elif row.role == "By-Product":
                row.notes = (
                    row.notes
                    or self.byproduct_description
                    or "منتج ثانوي ناتج من الفرز"
                )

            # Preserve the user-entered rate/amount for Manual costing.
            row.rate = flt(row.rate or 0)
            row.amount = flt(row.qty) * flt(row.rate)

    # ------------------------------------------------------------------
    # Quantities
    # ------------------------------------------------------------------

    def _calculate_totals(self):
        self.input_qty_total = sum(
            flt(row.qty)
            for row in (self.inputs or [])
        )

        self.output_qty_total = sum(
            flt(row.qty)
            for row in (self.outputs or [])
        )

        self.loss_qty = max(
            flt(self.input_qty_total)
            - flt(self.output_qty_total),
            0,
        )

        if self.input_qty_total:
            self.yield_percent = (
                flt(self.output_qty_total)
                / flt(self.input_qty_total)
                * 100
            )
        else:
            self.yield_percent = 0

    def _validate_quantities(self):
        if self.input_qty_total <= 0:
            frappe.throw(
                _("إجمالي كمية الإدخال يجب أن يكون أكبر من صفر.")
            )

        if self.output_qty_total <= 0:
            frappe.throw(
                _("إجمالي كمية المخرجات يجب أن يكون أكبر من صفر.")
            )

        allow_loss = getattr(
            self._sorting_operation,
            "allow_loss",
            1,
        )

        if self.loss_qty > 0 and not allow_loss:
            frappe.throw(
                _(
                    "يوجد فاقد مقداره {0} كجم، لكن عملية الفرز لا تسمح بالفاقد."
                ).format(flt(self.loss_qty))
            )

        threshold = flt(
            getattr(
                self._sorting_operation,
                "variance_threshold",
                0,
            )
        )

        variance_percent = 0

        if self.input_qty_total:
            variance_percent = (
                self.loss_qty
                / self.input_qty_total
                * 100
            )

        if threshold and variance_percent > threshold:
            if getattr(
                self._sorting_operation,
                "variance_requires_approval",
                0,
            ):
                self.status = "Ready"

    # ------------------------------------------------------------------
    # Costing
    # ------------------------------------------------------------------

    def _calculate_costs(self):
        self.direct_cost = sum(
            flt(row.amount)
            for row in (self.costs or [])
        )

        self.total_cost = (
            flt(self.direct_cost)
            + flt(self.overhead_cost)
        )

        if self.output_qty_total:
            self.cost_per_kg = (
                flt(self.total_cost)
                / flt(self.output_qty_total)
            )
        else:
            self.cost_per_kg = 0

        if not self.cost_center:
            self.cost_center = (
                getattr(
                    self._sorting_operation,
                    "default_cost_center",
                    None,
                )
                or getattr(
                    self._sorting_step,
                    "step_cost_center",
                    None,
                )
            )

    def _validate_manual_costs(self):
        method = getattr(self, "cost_allocation_method", None)
        if method != "Manual":
            return
        for row in (self.outputs or []):
            if row.role == "By-Product":
                continue
            if flt(row.qty) > 0 and flt(row.rate) <= 0:
                frappe.throw(
                    _("يجب إدخال تكلفة يدوية أكبر من صفر للمخرج {0}.").format(row.item)
                )

    # ------------------------------------------------------------------
    # Process Order Creation
    # ------------------------------------------------------------------

    def _create_process_order(self):
        if self.process_order:
            existing = frappe.db.get_value(
                "Coffee Process Order",
                self.process_order,
                ["docstatus", "stock_entry"],
                as_dict=True,
            )

            if existing and existing.docstatus == 1:
                frappe.throw(
                    _(
                        "أمر العملية {0} تم ترحيله مسبقًا."
                    ).format(self.process_order)
                )

        cpo = frappe.new_doc("Coffee Process Order")

        cpo.company = self.company
        cpo.branch = self.branch
        cpo.posting_date = self.posting_date

        cpo.route = self._route.name
        cpo.route_step_sequence = self._route_sequence
        cpo.operation = self._sorting_operation.name
        cpo.operation_code = SORTING_OPERATION_CODE
        cpo.operation_name_ar = (
            self._sorting_operation.operation_name_ar
            or "الفرز"
        )

        cpo.source_warehouse = (
            self.inputs[0].warehouse
        )

        cpo.target_warehouse = (
            self.outputs[0].warehouse
        )

        cpo.cost_center = (
            self.cost_center
            or getattr(
                self._sorting_step,
                "step_cost_center",
                None,
            )
            or getattr(
                self._sorting_operation,
                "default_cost_center",
                None,
            )
        )

        cpo.assigned_to = self.operator or None
        cpo.required_role = getattr(
            self._sorting_operation,
            "required_role",
            None,
        )

        cpo.weight_before = (
            flt(self.input_qty_total)
        )

        cpo.weight_after = (
            flt(self.output_qty_total)
        )

        cpo.quality_result = (
            "Approved"
            if self.sorting_grade
            else "Pending"
        )

        cpo.sample_reference = self.reject_reason or None

        cpo.approval_status = "Not Required"

        cpo.daily_monitoring_notes = self.remarks

        cpo.cost_allocation_method = (
            getattr(self, "cost_allocation_method", None)
            or getattr(self._sorting_operation, "cost_allocation_method", None)
            or "Same Input Cost"
        )

        cpo.variance_treatment_method = getattr(
            self._sorting_operation,
            "variance_treatment_method",
            None,
        )

        cpo.remarks = self.remarks

        # --------------------------------------------------------------
        # Inputs
        # --------------------------------------------------------------

        for row in self.inputs:
            child = cpo.append("inputs", {})

            child.item = row.item
            child.warehouse = row.warehouse
            child.batch_no = row.batch_no
            child.qty = flt(row.qty)

            child.uom = (
                frappe.db.get_value(
                    "Item",
                    row.item,
                    "stock_uom",
                )
                or "Kg"
            )

            child.conversion_factor = 1
            child.valuation_rate = flt(row.rate)
            child.amount = flt(row.amount)
            child.source_voucher_type = "Coffee Sorting Order"
            child.source_voucher_no = self.name
            child.is_reprocessing = 0
            child.coffee_batch = row.coffee_batch

        # --------------------------------------------------------------
        # Outputs
        # --------------------------------------------------------------

        for row in self.outputs:
            child = cpo.append("outputs", {})

            child.item = row.item
            child.warehouse = row.warehouse
            child.qty = flt(row.qty)

            child.uom = (
                frappe.db.get_value(
                    "Item",
                    row.item,
                    "stock_uom",
                )
                or "Kg"
            )

            child.conversion_factor = 1

            if row.role == "Reject":
                child.output_type = "Main Product"
                child.is_saleable = 1
            elif row.role == "By-Product":
                child.output_type = "By-Product"
                child.is_saleable = 0
            else:
                child.output_type = "Main Product"
                child.is_saleable = 1

            child.quality_status = "Pending"
            child.notes = row.notes
            child.valuation_rate = flt(row.rate)
            child.amount = flt(row.amount)

        # --------------------------------------------------------------
        # Sorting Costs -> Coffee Process Order
        # --------------------------------------------------------------
        # Sorting Order is the source of the operational costs entered
        # during sorting. CPO is the central processing-cost record.
        cpo.process_cost_total = flt(self.direct_cost)
        cpo.overhead_cost_total = flt(self.overhead_cost)

        # Preserve the detailed operational cost lines.
        for cost_row in (self.costs or []):
            cost_child = cpo.append("additional_costs", {})

            cost_child.expense_account = cost_row.account
            cost_child.description = cost_row.description
            cost_child.amount = flt(cost_row.amount)

        cpo.insert(
            ignore_permissions=True,
        )

        # حفظ الربط قبل الترحيل حتى يمكن التتبع.
        self.db_set(
            "process_order",
            cpo.name,
            update_modified=False,
        )

        cpo.submit()

        self.process_order = cpo.name
        self.stock_entry = cpo.stock_entry
        self.db_set(
            "stock_entry",
            cpo.stock_entry,
            update_modified=False,
        )

        return cpo

    # ------------------------------------------------------------------
    # Submit / Cancel
    # ------------------------------------------------------------------

    def before_submit(self):
        self._load_sorting_operation()
        self._load_route_context()

        self._calculate_totals()
        self._validate_quantities()

        # القياسات المطلوبة حسب Master.
        if getattr(
            self._sorting_operation,
            "requires_weight",
            0,
        ):
            if flt(self.input_qty_total) <= 0:
                frappe.throw(
                    _("عملية الفرز تتطلب تسجيل الوزن.")
                )

        if getattr(
            self._sorting_operation,
            "requires_quality",
            0,
        ):
            if not self.sorting_grade:
                frappe.throw(
                    _("عملية الفرز تتطلب تحديد نتيجة/درجة الجودة.")
                )

        # منع إنشاء حركة مباشرة من Sorting.
        self.stock_entry = None

    def on_submit(self):
        cpo = self._create_process_order()

        # بعد نجاح CPO + Stock Entry:
        # نعتبر أمر Sorting مكتملًا.
        self.db_set(
            "status",
            "Completed",
        )

        self.db_set(
            "stock_entry",
            cpo.stock_entry,
        )

        # --------------------------------------------------------------
        # Advance output Coffee Batches to next route step.
        # --------------------------------------------------------------
        if self._next_route_step and cpo.stock_entry:
            self._advance_output_batches(
                cpo,
                self._next_route_step,
            )

    def _advance_output_batches(
        self,
        cpo,
        next_step,
    ):
        """
        المحرك المركزي ينشئ Coffee Batch جديدة للمخرجات.
        بعد نجاح الفرز، ننقل الناتج إلى الخطوة التالية في المسار.
        """

        for row in cpo.outputs:
            if not row.coffee_batch:
                continue

            if not frappe.db.exists(
                "Coffee Batch",
                row.coffee_batch,
            ):
                continue

            batch = frappe.get_doc(
                "Coffee Batch",
                row.coffee_batch,
            )

            batch.current_step = next_step.sequence

            next_operation = frappe.db.get_value(
                "Coffee Process Route Step",
                {
                    "parent": self._route.name,
                    "sequence": next_step.sequence,
                },
                "operation",
            )

            if next_operation:
                batch.current_operation = frappe.db.get_value(
                    "Coffee Operation Master",
                    next_operation,
                    "operation_code",
                ) or next_operation

            batch.status = "Ready for Processing"

            batch.save(
                ignore_permissions=True,
            )

    def on_cancel(self):
        """
        لا ننشئ Stock Entry ولا نحاول تعديل المخزون مباشرة.

        إلغاء Sorting يلغي Coffee Process Order،
        وCoffee Process Order مسؤول عن إلغاء Stock Entry
        واستعادة Coffee Batch.
        """

        if not self.process_order:
            self.db_set(
                "status",
                "Cancelled",
            )
            return

        if not frappe.db.exists(
            "Coffee Process Order",
            self.process_order,
        ):
            self.db_set(
                "status",
                "Cancelled",
            )
            return

        cpo = frappe.get_doc(
            "Coffee Process Order",
            self.process_order,
        )

        if cpo.docstatus == 1:
            cpo.cancel()

        self.db_set(
            "status",
            "Cancelled",
        )

        self.db_set(
            "stock_entry",
            cpo.stock_entry,
        )
