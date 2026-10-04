import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CoffeeReceivingOrder(Document):

    def validate(self):
        self._validate_basic()
        self._calculate_totals()

    def _validate_basic(self):
        if not self.company:
            frappe.throw(_("الشركة مطلوبة."))

        if not self.supplier:
            frappe.throw(_("المورد مطلوب."))

        if not self.inputs:
            frappe.throw(_("يجب إضافة دفعة استلام واحدة على الأقل."))

        for row in self.inputs:
            if not row.coffee_batch and not row.item:
                frappe.throw(
                    _("يجب تحديد دفعة البن أو الصنف في كل سطر.")
                )

            if flt(row.qty) <= 0:
                frappe.throw(
                    _("كمية الاستلام يجب أن تكون أكبر من صفر.")
                )

            if row.coffee_batch:
                self._validate_batch(row.coffee_batch)

    def _validate_batch(self, batch_name):
        if not frappe.db.exists("Coffee Batch", batch_name):
            frappe.throw(
                _("دفعة البن غير موجودة: {0}").format(batch_name)
            )

        batch_company = frappe.db.get_value(
            "Coffee Batch",
            batch_name,
            "company"
        )

        if batch_company and batch_company != self.company:
            frappe.throw(
                _("الشركة في الدفعة لا تطابق الشركة في أمر الاستلام.")
            )

    def _calculate_totals(self):
        self.input_qty_total = sum(
            flt(row.qty)
            for row in self.inputs
        )

        self.output_qty_total = self.input_qty_total

        self.loss_qty = 0

        self.yield_percent = 100 if self.input_qty_total else 0

        direct_cost = 0

        for row in self.costs or []:
            if not flt(row.amount):
                row.amount = (
                    flt(row.qty) *
                    flt(row.rate)
                )

            direct_cost += flt(row.amount)

        self.direct_cost = direct_cost

        self.total_cost = (
            flt(self.direct_cost)
            + flt(self.overhead_cost)
            + flt(self.initial_rate) * self.input_qty_total
        )

        self.cost_per_kg = (
            self.total_cost / self.input_qty_total
            if self.input_qty_total
            else 0
        )

    def before_submit(self):
        self._create_or_link_batches()

    def _create_or_link_batches(self):
        """
        إنشاء Coffee Batch للدفعة المستلمة.
        لا يتم إنشاء Stock Entry هنا لأن Purchase Receipt
        هو المسؤول عن حركة مخزون الشراء.
        """

        for row in self.inputs:

            if row.coffee_batch:
                self._update_existing_batch(row)
                continue

            if not row.item:
                frappe.throw(
                    _("الصنف مطلوب لإنشاء دفعة الاستلام.")
                )

            batch_name = self._find_existing_source_batch(row)

            if batch_name:
                row.coffee_batch = batch_name
                self._update_existing_batch(row)
                continue

            batch = frappe.new_doc("Coffee Batch")

            batch.custom_item_code = row.item

            batch.item_name = (
                frappe.db.get_value(
                    "Item",
                    row.item,
                    "item_name"
                )
                or row.item
            )

            batch.coffee_type = (
                self.coffee_type
                or "Commercial"
            )

            batch.company = self.company
            batch.branch = self.branch

            batch.source_type = "Purchase"

            batch.supplier = self.supplier
            batch.purchase_receipt = self.purchase_receipt

            batch.current_warehouse = row.warehouse

            batch.qty = flt(row.qty)

            batch.valuation_rate = (
                flt(row.rate)
                or flt(self.initial_rate)
            )

            batch.cost_per_kg = batch.valuation_rate

            batch.total_value = (
                flt(batch.qty) *
                flt(batch.valuation_rate)
            )

            batch.status = "Received"

            batch.cost_center = self.cost_center

            batch.insert(ignore_permissions=True)

            row.coffee_batch = batch.name

            self._create_purchase_source(row, batch)

    def _find_existing_source_batch(self, row):
        if not self.purchase_receipt:
            return None

        filters = {
            "purchase_receipt": self.purchase_receipt,
            "supplier": self.supplier,
            "custom_item_code": row.item,
            "company": self.company,
        }

        return frappe.db.get_value(
            "Coffee Batch",
            filters,
            "name"
        )

    def _update_existing_batch(self, row):
        batch = frappe.get_doc(
            "Coffee Batch",
            row.coffee_batch
        )

        if not batch.company:
            batch.company = self.company

        if not batch.supplier:
            batch.supplier = self.supplier

        if not batch.purchase_receipt:
            batch.purchase_receipt = self.purchase_receipt

        if not batch.current_warehouse:
            batch.current_warehouse = row.warehouse

        if flt(batch.qty) <= 0:
            batch.qty = flt(row.qty)

        if flt(batch.valuation_rate) <= 0:
            batch.valuation_rate = (
                flt(row.rate)
                or flt(self.initial_rate)
            )

        if flt(batch.cost_per_kg) <= 0:
            batch.cost_per_kg = batch.valuation_rate

        if flt(batch.total_value) <= 0:
            batch.total_value = (
                flt(batch.qty) *
                flt(batch.valuation_rate)
            )

        batch.save(ignore_permissions=True)

        self._create_purchase_source(row, batch)

    def _create_purchase_source(self, row, batch):
        if not frappe.db.exists(
            "Coffee Batch Purchase Source",
            {
                "parent": batch.name,
                "parenttype": "Coffee Batch",
                "purchase_receipt": self.purchase_receipt,
            }
        ):
            source = batch.append(
                "purchase_sources",
                {}
            )

            source.purchase_receipt = (
                self.purchase_receipt
            )

            source.purchase_receipt_item = (
                row.purchase_receipt_item
            )

            source.purchase_invoice = (
                self.purchase_invoice
            )

            source.supplier = self.supplier
            source.item = row.item
            source.qty = row.qty
            source.rate = (
                flt(row.rate)
                or flt(self.initial_rate)
            )

            source.amount = (
                flt(source.qty) *
                flt(source.rate)
            )

            source.erpnext_batch = (
                batch.erpnext_batch
            )

            batch.save(ignore_permissions=True)

    def on_submit(self):
        self.db_set("status", "Completed")

    def on_cancel(self):
        self.db_set("status", "Cancelled")

    @frappe.whitelist()
    def create_batches(self):
        """
        يسمح بإنشاء/ربط الدفعات قبل Submit
        من زر واجهة المستخدم.
        """

        if self.docstatus != 0:
            frappe.throw(
                _("يمكن تنفيذ هذه العملية للمستند غير المرسل فقط.")
            )

        self._create_or_link_batches()

        self.save(ignore_permissions=True)

        return {
            "name": self.name,
            "batches": [
                row.coffee_batch
                for row in self.inputs
                if row.coffee_batch
            ]
        }
