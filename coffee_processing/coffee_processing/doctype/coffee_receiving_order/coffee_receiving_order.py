import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


RAW_ITEM_NAMES = {
    "001",
    "COF-004",
}


class CoffeeReceivingOrder(Document):

    def validate(self):
        self._validate_header()
        self._load_receiving_settings()
        self._validate_inputs()
        self._validate_single_item()
        self._validate_source_warehouse()
        self._validate_quantities()
        self._calculate_totals()

    # ------------------------------------------------------------------
    # HEADER
    # ------------------------------------------------------------------

    def _validate_header(self):
        if not self.company:
            frappe.throw(_("الشركة مطلوبة."))

        if not self.supplier:
            frappe.throw(_("المورد مطلوب."))

        if not self.posting_date:
            self.posting_date = nowdate()

        if not self.inputs:
            frappe.throw(_("يجب إضافة دفعة استلام واحدة على الأقل."))

    # ------------------------------------------------------------------
    # SETTINGS
    # ------------------------------------------------------------------

    def _load_receiving_settings(self):
        filters = {
            "company": self.company,
            "active": 1,
        }

        if self.branch:
            filters["branch"] = self.branch

        settings_name = frappe.db.get_value(
            "Coffee Receiving Settings",
            filters,
            "name",
            order_by="modified desc",
        )

        if not settings_name:
            frappe.throw(
                _(
                    "لا توجد إعدادات استلام فعالة للشركة {0}"
                    "{1}. قم بإنشاء Coffee Receiving Settings أولاً."
                ).format(
                    self.company,
                    _(" والفرع {0}").format(self.branch)
                    if self.branch
                    else "",
                )
            )

        settings = frappe.get_doc(
            "Coffee Receiving Settings",
            settings_name,
        )

        if not settings.source_warehouse:
            frappe.throw(_("مخزن المصدر في إعدادات الاستلام غير محدد."))

        if not settings.target_warehouse:
            frappe.throw(_("مخزن الهدف في إعدادات الاستلام غير محدد."))

        if settings.source_warehouse == settings.target_warehouse:
            frappe.throw(
                _("مخزن المصدر ومخزن الهدف يجب أن يكونا مختلفين.")
            )

        self._receiving_settings = settings
        self._configured_source_warehouse = settings.source_warehouse
        self._configured_target_warehouse = settings.target_warehouse

    # ------------------------------------------------------------------
    # INPUT VALIDATION
    # ------------------------------------------------------------------

    def _validate_inputs(self):
        for row in self.inputs:
            if not row.item and not row.coffee_batch:
                frappe.throw(
                    _("يجب تحديد الصنف أو Coffee Batch في كل سطر.")
                )

            if flt(row.qty) <= 0:
                frappe.throw(
                    _("كمية الاستلام يجب أن تكون أكبر من صفر.")
                )

            if row.coffee_batch:
                self._validate_coffee_batch(row)
            elif row.item:
                self._validate_item(row)

    def _validate_single_item(self):
        items = set()

        for row in self.inputs:
            item_code = row.item

            if not item_code and row.coffee_batch:
                item_code = frappe.db.get_value(
                    "Coffee Batch",
                    row.coffee_batch,
                    "custom_item_code",
                )

            if item_code:
                items.add(item_code)

        if len(items) != 1:
            frappe.throw(
                _(
                    "أمر الاستلام يجب أن يحتوي على صنف واحد فقط. "
                    "لا يمكن خلط البن الخام والبن القاصي في نفس الأمر."
                )
            )

        self._receiving_item = next(iter(items))

        if self._receiving_item not in RAW_ITEM_NAMES:
            frappe.throw(
                _(
                    "الصنف {0} غير مسموح في Coffee Receiving Order. "
                    "الاستلام يبدأ فقط من البن الخام أو البن القاصي."
                ).format(self._receiving_item)
            )

    def _validate_item(self, row):
        if row.item not in RAW_ITEM_NAMES:
            frappe.throw(
                _(
                    "الصنف {0} غير مسموح في الاستلام. "
                    "المسموح: البن الخام أو البن القاصي."
                ).format(row.item)
            )

        item_data = frappe.db.get_value(
            "Item",
            row.item,
            ["disabled", "is_stock_item", "has_batch_no"],
            as_dict=True,
        )

        if not item_data:
            frappe.throw(_("الصنف غير موجود: {0}").format(row.item))

        if item_data.disabled:
            frappe.throw(_("الصنف {0} معطل.").format(row.item))

        if not item_data.is_stock_item:
            frappe.throw(_("الصنف {0} ليس صنف مخزون.").format(row.item))

        if not item_data.has_batch_no:
            frappe.throw(
                _("الصنف {0} يجب أن يكون Batch Item.").format(row.item)
            )

    # ------------------------------------------------------------------
    # COFFEE BATCH
    # ------------------------------------------------------------------

    def _validate_coffee_batch(self, row):
        batch = frappe.get_doc(
            "Coffee Batch",
            row.coffee_batch,
        )

        item_code = batch.custom_item_code

        if not item_code:
            frappe.throw(
                _("Coffee Batch {0} لا يحتوي على صنف.").format(
                    batch.name
                )
            )

        if item_code not in RAW_ITEM_NAMES:
            frappe.throw(
                _(
                    "Coffee Batch {0} ليس دفعة بن خام أو بن قاصي."
                ).format(batch.name)
            )

        if batch.company and batch.company != self.company:
            frappe.throw(
                _(
                    "الشركة في الدفعة {0} لا تطابق الشركة في أمر الاستلام."
                ).format(batch.name)
            )

        if batch.supplier and batch.supplier != self.supplier:
            frappe.throw(
                _(
                    "المورد في الدفعة {0} لا يطابق المورد في أمر الاستلام."
                ).format(batch.name)
            )

        if row.item and row.item != item_code:
            frappe.throw(
                _(
                    "الصنف في السطر لا يطابق صنف Coffee Batch {0}."
                ).format(batch.name)
            )

        row.item = item_code

        erp_batch = getattr(batch, "erpnext_batch", None)

        if not erp_batch:
            frappe.throw(
                _(
                    "Coffee Batch {0} لا يرتبط بـ ERPNext Batch."
                ).format(batch.name)
            )

        batch_item = frappe.db.get_value(
            "Batch",
            erp_batch,
            "item",
        )

        if not batch_item:
            frappe.throw(
                _("ERPNext Batch غير موجود: {0}").format(erp_batch)
            )

        if batch_item != item_code:
            frappe.throw(
                _(
                    "ERPNext Batch {0} لا يطابق الصنف {1}."
                ).format(erp_batch, item_code)
            )

    # ------------------------------------------------------------------
    # SOURCE WAREHOUSE
    # ------------------------------------------------------------------

    def _validate_source_warehouse(self):
        configured_source = self._configured_source_warehouse

        wh = frappe.db.get_value(
            "Warehouse",
            configured_source,
            ["company", "is_group", "disabled"],
            as_dict=True,
        )

        if not wh:
            frappe.throw(
                _("مخزن المصدر غير موجود: {0}").format(
                    configured_source
                )
            )

        if wh.disabled:
            frappe.throw(
                _("مخزن المصدر معطل: {0}").format(
                    configured_source
                )
            )

        if wh.is_group:
            frappe.throw(
                _("لا يمكن استخدام مخزن رئيسي كمصدر للاستلام: {0}").format(
                    configured_source
                )
            )

        if wh.company != self.company:
            frappe.throw(
                _("مخزن المصدر {0} لا يتبع الشركة {1}.").format(
                    configured_source,
                    self.company,
                )
            )

        for row in self.inputs:
            if row.warehouse and row.warehouse != configured_source:
                frappe.throw(
                    _(
                        "مخزن المصدر في السطر {0} يجب أن يطابق "
                        "مخزن المصدر المحدد في إعدادات الاستلام."
                    ).format(row.idx)
                )

            row.warehouse = configured_source

    # ------------------------------------------------------------------
    # QUANTITY / SABB AVAILABILITY
    # ------------------------------------------------------------------

    def _validate_quantities(self):
        for row in self.inputs:
            if not row.coffee_batch:
                frappe.throw(
                    _("يجب اختيار Coffee Batch لكل سطر استلام.")
                )

            batch = frappe.get_doc(
                "Coffee Batch",
                row.coffee_batch,
            )

            erp_batch = getattr(batch, "erpnext_batch", None)

            if not erp_batch:
                frappe.throw(
                    _("Coffee Batch {0} لا يحتوي على ERPNext Batch.").format(
                        batch.name
                    )
                )

            available = self._get_available_source_qty(
                batch.custom_item_code,
                erp_batch,
            )

            requested = flt(row.qty)

            if requested > available + 0.0001:
                frappe.throw(
                    _(
                        "الكمية المطلوبة {0} كجم للدفعة {1} "
                        "أكبر من الكمية المتاحة للاستلام {2} كجم."
                    ).format(
                        requested,
                        batch.name,
                        available,
                    )
                )

            if flt(batch.qty) + 0.0001 < requested:
                frappe.throw(
                    _(
                        "كمية Coffee Batch {0} ({1}) أقل من الكمية "
                        "المطلوبة للاستلام ({2})."
                    ).format(
                        batch.name,
                        flt(batch.qty),
                        requested,
                    )
                )

            row.rate = (
                flt(row.rate)
                or flt(batch.valuation_rate)
                or 0
            )

            row.batch_no = erp_batch

    def _get_available_source_qty(self, item, erpnext_batch):
        if not item or not erpnext_batch:
            return 0.0

        source_warehouse = self._configured_source_warehouse

        if not source_warehouse:
            return 0.0

        batch_item = frappe.db.get_value(
            "Batch",
            erpnext_batch,
            "item",
        )

        if not batch_item:
            frappe.throw(
                _("ERPNext Batch غير موجود: {0}").format(
                    erpnext_batch
                )
            )

        if batch_item != item:
            frappe.throw(
                _(
                    "ERPNext Batch {0} مرتبط بالصنف {1} وليس {2}."
                ).format(
                    erpnext_batch,
                    batch_item,
                    item,
                )
            )

        result = frappe.db.sql(
            """
            SELECT
                COALESCE(SUM(e.qty), 0) AS qty
            FROM `tabSerial and Batch Entry` e
            INNER JOIN `tabSerial and Batch Bundle` b
                ON b.name = e.parent
            WHERE b.docstatus = 1
              AND IFNULL(b.is_cancelled, 0) = 0
              AND IFNULL(b.is_rejected, 0) = 0
              AND e.batch_no = %s
              AND e.warehouse = %s
            """,
            (
                erpnext_batch,
                source_warehouse,
            ),
            as_dict=True,
        )

        return max(
            flt(result[0].qty if result else 0),
            0,
        )

    # ------------------------------------------------------------------
    # TOTALS
    # ------------------------------------------------------------------

    def _calculate_totals(self):
        self.input_qty_total = sum(
            flt(row.qty)
            for row in self.inputs
        )

        self.output_qty_total = self.input_qty_total
        self.loss_qty = 0

        self.yield_percent = (
            100
            if self.input_qty_total
            else 0
        )

        direct_cost = 0

        for row in self.costs or []:
            if not flt(row.amount):
                row.amount = (
                    flt(row.qty)
                    * flt(row.rate)
                )

            direct_cost += flt(row.amount)

        self.direct_cost = direct_cost

        purchase_value = sum(
            flt(row.qty) * flt(row.rate)
            for row in self.inputs
        )

        self.total_cost = (
            purchase_value
            + flt(self.overhead_cost)
            + flt(self.direct_cost)
        )

        self.cost_per_kg = (
            self.total_cost / self.input_qty_total
            if self.input_qty_total
            else 0
        )

    # ------------------------------------------------------------------
    # SUBMIT
    # ------------------------------------------------------------------

    def before_submit(self):
        self._validate_quantities()
        self._prepare_receiving_batches()
        self._create_stock_entry()

    def _prepare_receiving_batches(self):
        """
        Prepare the Coffee Batch representing the quantity that will
        physically move from CRW to CPW.

        Full receipt:
            Original Coffee Batch moves to CPW.

        Partial receipt:
            Original Coffee Batch keeps the remaining quantity in CRW.
            A new Split Coffee Batch represents the transferred quantity
            in CPW.
        """
        for row in self.inputs:
            batch = frappe.get_doc("Coffee Batch", row.coffee_batch)

            requested = flt(row.qty)
            current_qty = flt(batch.qty)

            if requested <= 0:
                frappe.throw(_("كمية الاستلام يجب أن تكون أكبر من صفر."))

            if requested > current_qty + 0.0001:
                frappe.throw(
                    _("الكمية المطلوبة {0} أكبر من كمية الدفعة {1}.").format(
                        requested,
                        current_qty,
                    )
                )

            # Do not split a batch that is already in another warehouse
            # or already in processing.
            if batch.current_warehouse != self._configured_source_warehouse:
                frappe.throw(
                    _(
                        "Coffee Batch {0} ليست موجودة في مخزن المصدر {1}."
                    ).format(
                        batch.name,
                        self._configured_source_warehouse,
                    )
                )

            if batch.status not in ("Received",):
                frappe.throw(
                    _(
                        "لا يمكن استلام Coffee Batch {0} لأن حالتها الحالية هي {1}."
                    ).format(
                        batch.name,
                        batch.status,
                    )
                )

            # Full receipt: keep the original Coffee Batch.
            if requested >= current_qty - 0.0001:
                row.coffee_batch = batch.name
                continue

            # Partial receipt: create a processing batch.
            processing_batch = frappe.new_doc("Coffee Batch")

            processing_batch.custom_item_code = batch.custom_item_code
            processing_batch.item_name = batch.item_name
            processing_batch.coffee_type = batch.coffee_type
            processing_batch.company = batch.company
            processing_batch.branch = batch.branch
            processing_batch.source_type = "Split"
            processing_batch.supplier = batch.supplier
            processing_batch.purchase_receipt = batch.purchase_receipt
            processing_batch.parent_batch = batch.name
            processing_batch.split_from = batch.name
            processing_batch.route = batch.route
            processing_batch.cost_center = batch.cost_center
            processing_batch.current_warehouse = (
                self._configured_target_warehouse
            )
            processing_batch.qty = requested
            processing_batch.valuation_rate = flt(batch.valuation_rate)
            processing_batch.cost_per_kg = flt(batch.valuation_rate)
            processing_batch.total_value = (
                requested * flt(batch.valuation_rate)
            )
            processing_batch.reserved_qty = 0
            processing_batch.erpnext_batch = batch.erpnext_batch
            processing_batch.status = "Ready for Processing"
            processing_batch.created_by = frappe.session.user
            processing_batch.creation_date = frappe.utils.nowdate()
            processing_batch.notes = _(
                "دفعة معالجة ناتجة عن استلام جزئي من {0} بواسطة أمر الاستلام {1}."
            ).format(
                batch.name,
                self.name,
            )

            processing_batch.insert(ignore_permissions=True)

            source_row = processing_batch.append(
                "source_batches",
                {},
            )
            source_row.source_batch = batch.name
            source_row.qty_consumed = requested
            source_row.cost_amount = (
                requested * flt(batch.valuation_rate)
            )

            processing_batch.save(ignore_permissions=True)

            # Reduce the original source Coffee Batch.
            batch.qty = current_qty - requested
            batch.total_value = (
                batch.qty * flt(batch.valuation_rate)
            )
            batch.current_warehouse = (
                self._configured_source_warehouse
            )
            batch.status = "Received"
            batch.save(ignore_permissions=True)

            # The Stock Entry must use the new processing batch.
            row.coffee_batch = processing_batch.name
            row.item = processing_batch.custom_item_code
            row.batch_no = processing_batch.erpnext_batch

    def on_submit(self):
        self._update_batch_after_submit()
        self.db_set("status", "Completed")

    # ------------------------------------------------------------------
    # STOCK ENTRY
    # ------------------------------------------------------------------

    def _create_stock_entry(self):
        if self.stock_entry:
            frappe.throw(
                _("يوجد Stock Entry مرتبط مسبقاً بأمر الاستلام.")
            )

        source = self._configured_source_warehouse
        target = self._configured_target_warehouse

        if not source or not target:
            frappe.throw(
                _("مخزن المصدر والهدف غير محددين.")
            )

        se = frappe.new_doc("Stock Entry")
        se.stock_entry_type = "Material Transfer"
        se.company = self.company
        se.posting_date = self.posting_date
        se.posting_time = frappe.utils.nowtime()

        if self.branch and hasattr(se, "branch"):
            se.branch = self.branch

        if hasattr(se, "remarks"):
            se.remarks = _(
                "Coffee Receiving Order: {0}"
            ).format(self.name)

        for row in self.inputs:
            batch = frappe.get_doc(
                "Coffee Batch",
                row.coffee_batch,
            )

            erp_batch = batch.erpnext_batch

            if not erp_batch:
                frappe.throw(
                    _("لا يوجد ERPNext Batch للدفعة {0}.").format(
                        batch.name
                    )
                )

            se.append(
                "items",
                {
                    "item_code": row.item,
                    "qty": flt(row.qty),
                    "uom": frappe.db.get_value(
                        "Item",
                        row.item,
                        "stock_uom",
                    ),
                    "stock_uom": frappe.db.get_value(
                        "Item",
                        row.item,
                        "stock_uom",
                    ),
                    "conversion_factor": 1,
                    "s_warehouse": source,
                    "t_warehouse": target,
                    "batch_no": erp_batch,
                    "basic_rate": flt(row.rate),
                    "set_basic_rate_manually": 1,
                },
            )

        if not se.items:
            frappe.throw(
                _("لا توجد بنود لإنشاء Stock Entry.")
            )

        se.insert(ignore_permissions=True)
        se.submit()

        self.db_set(
            "stock_entry",
            se.name,
        )

    # ------------------------------------------------------------------
    # BATCH STATE
    # ------------------------------------------------------------------

    def _update_batch_after_submit(self):
        for row in self.inputs:
            batch = frappe.get_doc(
                "Coffee Batch",
                row.coffee_batch,
            )

            # A partial receipt already reduced the original batch and
            # created this processing batch before Stock Entry creation.
            # Therefore do NOT reduce its quantity again.
            if (
                getattr(batch, "source_type", None) == "Split"
                and getattr(batch, "split_from", None)
            ):
                batch.current_warehouse = (
                    self._configured_target_warehouse
                )
                batch.status = "Ready for Processing"
                batch.save(ignore_permissions=True)
                continue

            # Full receipt: the original purchase batch itself moves
            # from CRW to the processing warehouse.
            batch.current_warehouse = (
                self._configured_target_warehouse
            )
            batch.status = "Ready for Processing"
            batch.save(ignore_permissions=True)

    # ------------------------------------------------------------------
    # CANCEL
    # ------------------------------------------------------------------

    def before_cancel(self):
        """
        Validate cancellation before the document is cancelled.

        Stock Entry cancellation is intentionally handled in on_cancel()
        after the Receiving Order cancellation lifecycle has progressed.
        """
        if self.stock_entry:
            se = frappe.get_doc("Stock Entry", self.stock_entry)

            if se.docstatus not in (0, 2):
                # The Stock Entry must still be cancellable.
                # It will be cancelled by on_cancel().
                pass

    def on_cancel(self):
        """
        Reverse a submitted Coffee Receiving Order.

        Full receipt:
            Restore the original Coffee Batch to the source warehouse.

        Partial receipt:
            The input row points to the Split Coffee Batch.
            Delete that split batch when it has no downstream usage,
            then restore the consumed quantity to its parent batch.
        """
        # cancel() does not run validate(), so reload the settings
        # before using the configured source/target warehouses.
        self._load_receiving_settings()

        # Cancel the linked Stock Entry as part of the Receiving Order
        # cancellation lifecycle. This is intentionally done here,
        # not in before_cancel(), to avoid Frappe link validation errors.
        if self.stock_entry:
            stock_entry = frappe.get_doc("Stock Entry", self.stock_entry)
            if stock_entry.docstatus == 1:
                stock_entry.cancel()

        self.db_set("status", "Cancelled")

        for row in self.inputs:
            moved_qty = flt(row.qty)

            if moved_qty <= 0:
                continue

            row_batch = frappe.get_doc("Coffee Batch", row.coffee_batch)

            # Partial receiving: the row points to the Split Batch.
            if (
                getattr(row_batch, "source_type", None) == "Split"
                and getattr(row_batch, "split_from", None)
            ):
                parent_name = row_batch.split_from
                parent_batch = frappe.get_doc("Coffee Batch", parent_name)

                # Never reverse a split that has already entered
                # a downstream operation.
                downstream_count = frappe.db.count(
                    "Coffee Batch Source",
                    {
                        "source_batch": row_batch.name,
                    },
                )

                if downstream_count:
                    frappe.throw(
                        _(
                            "لا يمكن إلغاء أمر الاستلام {0} لأن الدفعة الجزئية {1} "
                            "دخلت في عمليات لاحقة."
                        ).format(
                            self.name,
                            row_batch.name,
                        )
                    )

                # Restore the quantity to the original source batch.
                parent_batch.qty = flt(parent_batch.qty) + moved_qty
                parent_batch.total_value = (
                    flt(parent_batch.qty)
                    * flt(parent_batch.valuation_rate)
                )
                parent_batch.current_warehouse = (
                    self._configured_source_warehouse
                )
                parent_batch.status = "Received"
                parent_batch.save(ignore_permissions=True)

                # Remove the temporary processing split.
                frappe.delete_doc(
                    "Coffee Batch",
                    row_batch.name,
                    ignore_permissions=True,
                    force=True,
                )

                continue

            # Full receipt: restore the original batch.
            row_batch.qty = flt(row_batch.qty) + moved_qty
            row_batch.total_value = (
                flt(row_batch.qty)
                * flt(row_batch.valuation_rate)
            )
            row_batch.current_warehouse = (
                self._configured_source_warehouse
            )
            row_batch.status = "Received"
            row_batch.save(ignore_permissions=True)

    def create_batches(self):
        if self.docstatus != 0:
            frappe.throw(
                _(
                    "يمكن تنفيذ هذه العملية للمستند غير المرسل فقط."
                )
            )

        self.validate()

        return {
            "name": self.name,
            "batches": [
                row.coffee_batch
                for row in self.inputs
                if row.coffee_batch
            ],
        }
