# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.utils import flt


class CostAllocationService:
    """
    مسؤول عن توزيع تكلفة عملية المعالجة على المخرجات الفعلية.

    المبادئ:
    1. التكلفة تعتمد على Actual Input وليس Planned Input.
    2. المخرج Loss لا يحصل على Batch ولا يدخل كمنتج قابل للتكلفة.
    3. كل Output يحصل على Rate فعلي قبل إنشاء Coffee Batch.
    4. لا توجد أسعار افتراضية مثل 1 أو 1.5.
    5. Hybrid يوزع:
       - Material Cost حسب الكمية.
       - Processing Cost حسب القيمة النسبية.
    """

    @staticmethod
    def allocate_costs(doc):
        """
        حساب وتوزيع تكلفة أمر المعالجة.

        Returns:
            dict يحتوي إجمالي التكلفة والمبالغ الموزعة.
        """

        if not doc.operation:
            frappe.throw(_("Operation is required for cost allocation"))

        operation = frappe.get_doc(
            "Coffee Operation Master",
            doc.operation,
        )

        method = (
            doc.cost_allocation_method
            or operation.cost_allocation_method
            or "Quantity Based"
        )

        # -----------------------------------------------------
        # Material / Input Cost
        # -----------------------------------------------------

        input_cost = flt(
            sum(
                flt(i.amount)
                for i in doc.inputs
            )
        )

        # -----------------------------------------------------
        # Processing Cost
        # -----------------------------------------------------

        process_cost = flt(
            flt(doc.labor_cost)
            + flt(doc.machine_cost)
            + flt(doc.electricity_cost)
            + flt(doc.other_cost)
        )

        total_cost = flt(
            input_cost + process_cost
        )

        # -----------------------------------------------------
        # Outputs
        #
        # Loss لا يعتبر منتجًا قابلًا للتكلفة.
        # -----------------------------------------------------

        costable_outputs = [
            o
            for o in doc.outputs
            if (o.output_type or "") != "Loss"
            and flt(o.actual_qty) > 0
        ]

        if not costable_outputs:
            if total_cost > 0:
                frappe.throw(
                    _(
                        "The processing order has a cost of {0}, "
                        "but no costable output was recorded."
                    ).format(total_cost)
                )

            return {
                "method": method,
                "input_cost": input_cost,
                "process_cost": process_cost,
                "total_cost": total_cost,
                "allocated_cost": 0,
            }

        # -----------------------------------------------------
        # اختيار طريقة التوزيع
        # -----------------------------------------------------

        if method == "Quantity Based":

            CostAllocationService._allocate_by_quantity(
                costable_outputs,
                total_cost,
            )

        elif method == "Relative Sales Value":

            CostAllocationService._allocate_by_sales_value(
                costable_outputs,
                total_cost,
            )

        elif method == "By-Product Credit":

            CostAllocationService._allocate_by_product_credit(
                costable_outputs,
                total_cost,
                process_cost,
            )

        elif method == "Hybrid":

            CostAllocationService._allocate_hybrid(
                costable_outputs,
                input_cost,
                process_cost,
            )

        elif method == "Manual":

            CostAllocationService._allocate_manually(
                costable_outputs,
                total_cost,
            )

        else:

            frappe.throw(
                _(
                    "Unsupported cost allocation method: {0}"
                ).format(method)
            )

        # -----------------------------------------------------
        # Reload output values after db_set
        # -----------------------------------------------------

        allocated_cost = flt(
            sum(
                flt(o.amount)
                for o in costable_outputs
            )
        )

        return {
            "method": method,
            "input_cost": input_cost,
            "process_cost": process_cost,
            "total_cost": total_cost,
            "allocated_cost": allocated_cost,
        }

    # =========================================================
    # Quantity Based
    # =========================================================

    @staticmethod
    def _allocate_by_quantity(outputs, total_cost):
        """
        توزيع التكلفة حسب Actual Output Quantity.

        مثال:
            Total Cost = 100,000
            G14 = 600 kg
            G16 = 300 kg
            G17 = 100 kg

            Total = 1,000 kg

            Rate = 100 / kg
        """

        total_qty = flt(
            sum(
                flt(o.actual_qty)
                for o in outputs
            )
        )

        if total_qty <= 0:
            frappe.throw(
                _("Total output quantity must be greater than zero")
            )

        cost_per_kg = flt(
            total_cost / total_qty
        )

        for output in outputs:

            qty = flt(output.actual_qty)

            amount = flt(
                qty * cost_per_kg
            )

            percentage = (
                (amount / total_cost) * 100
                if total_cost > 0
                else 0
            )

            output.db_set(
                "rate",
                cost_per_kg,
            )

            output.db_set(
                "amount",
                amount,
            )

            output.db_set(
                "cost_allocation_percentage",
                percentage,
            )

    # =========================================================
    # Relative Sales Value
    # =========================================================

    @staticmethod
    def _allocate_by_sales_value(outputs, total_cost):
        """
        توزيع التكلفة حسب القيمة البيعية النسبية.

        لا يتم استخدام قيمة افتراضية.

        إذا لم يوجد سعر بيع حقيقي:
        يتم إيقاف العملية برسالة واضحة.
        """

        total_value = 0
        values = {}

        for output in outputs:

            price = get_output_selling_price(output)

            if price <= 0:
                frappe.throw(
                    _(
                        "Selling price is required for output "
                        "{0} when using Relative Sales Value."
                    ).format(
                        output.item_code
                        or output.item_name
                        or output.coffee_grade
                        or output.output_type
                    )
                )

            value = flt(
                output.actual_qty * price
            )

            values[output.name] = value
            total_value += value

        if total_value <= 0:
            frappe.throw(
                _("Total relative sales value must be greater than zero")
            )

        for output in outputs:

            ratio = flt(
                values[output.name] / total_value
            )

            amount = flt(
                total_cost * ratio
            )

            qty = flt(
                output.actual_qty
            )

            rate = (
                amount / qty
                if qty > 0
                else 0
            )

            output.db_set(
                "amount",
                amount,
            )

            output.db_set(
                "rate",
                rate,
            )

            output.db_set(
                "cost_allocation_percentage",
                ratio * 100,
            )

    # =========================================================
    # By-Product Credit
    # =========================================================

    @staticmethod
    def _allocate_by_product_credit(
        outputs,
        total_cost,
        process_cost,
    ):
        """
        By-Product Credit:

        1. يتم تقييم الـ By-Product بقيمته البيعية الحقيقية.
        2. قيمته تعتبر Credit على تكلفة المنتجات الرئيسية.
        3. التكلفة الصافية للـ Main Outputs:
              Total Cost - By Product Credit

        لا يوجد fallback مثل 10%.
        """

        main_outputs = [
            o
            for o in outputs
            if (o.output_type or "") == "Main"
        ]

        by_products = [
            o
            for o in outputs
            if (o.output_type or "") == "By-Product"
        ]

        # -----------------------------------------------------
        # تقييم By-Products
        # -----------------------------------------------------

        by_product_credit = 0

        for bp in by_products:

            price = get_output_selling_price(bp)

            if price <= 0:
                frappe.throw(
                    _(
                        "Selling price is required for by-product "
                        "{0} when using By-Product Credit."
                    ).format(
                        bp.item_code
                        or bp.item_name
                        or bp.coffee_grade
                        or bp.output_type
                    )
                )

            qty = flt(
                bp.actual_qty
            )

            amount = flt(
                qty * price
            )

            bp.db_set(
                "rate",
                price,
            )

            bp.db_set(
                "amount",
                amount,
            )

            by_product_credit += amount

        # -----------------------------------------------------
        # التكلفة الصافية للـ Main
        # -----------------------------------------------------

        net_cost = flt(
            total_cost - by_product_credit
        )

        # -----------------------------------------------------
        # إذا كان الـ Credit أكبر من التكلفة
        #
        # لا نخترع 10%.
        # تصبح تكلفة Main = صفر.
        # الفرق يعتبر Gain اقتصاديًا وليس تكلفة مصطنعة.
        # -----------------------------------------------------

        if net_cost < 0:
            net_cost = 0

        # -----------------------------------------------------
        # توزيع صافي التكلفة على Main Outputs
        # -----------------------------------------------------

        if main_outputs:

            CostAllocationService._allocate_by_quantity(
                main_outputs,
                net_cost,
            )

        elif net_cost > 0:

            frappe.throw(
                _(
                    "By-Product Credit requires at least one "
                    "Main output."
                )
            )

    # =========================================================
    # Hybrid
    # =========================================================

    @staticmethod
    def _allocate_hybrid(
        outputs,
        input_cost,
        process_cost,
    ):
        """
        Hybrid:

        Material Cost
            -> Quantity Based

        Processing Cost
            -> Relative Sales Value

        لذلك:
            Material Allocation
            +
            Processing Allocation
            =
            Output Total Cost
        """

        total_qty = flt(
            sum(
                flt(o.actual_qty)
                for o in outputs
            )
        )

        if total_qty <= 0:
            frappe.throw(
                _("Total output quantity must be greater than zero")
            )

        # -----------------------------------------------------
        # حساب القيمة البيعية
        # -----------------------------------------------------

        values = {}
        total_value = 0

        for output in outputs:

            price = get_output_selling_price(output)

            if price <= 0:
                frappe.throw(
                    _(
                        "Selling price is required for output "
                        "{0} when using Hybrid cost allocation."
                    ).format(
                        output.item_code
                        or output.item_name
                        or output.coffee_grade
                        or output.output_type
                    )
                )

            value = flt(
                output.actual_qty * price
            )

            values[output.name] = value
            total_value += value

        if total_value <= 0:
            frappe.throw(
                _("Total sales value must be greater than zero")
            )

        # -----------------------------------------------------
        # التوزيع
        # -----------------------------------------------------

        for output in outputs:

            qty = flt(
                output.actual_qty
            )

            qty_ratio = flt(
                qty / total_qty
            )

            value_ratio = flt(
                values[output.name] / total_value
            )

            # Material
            material_amount = flt(
                input_cost * qty_ratio
            )

            # Processing
            processing_amount = flt(
                process_cost * value_ratio
            )

            total_amount = flt(
                material_amount
                + processing_amount
            )

            rate = (
                total_amount / qty
                if qty > 0
                else 0
            )

            # النسبة تمثل إجمالي مساهمة المخرج في التكلفة
            total_cost = (
                input_cost + process_cost
            )

            percentage = (
                total_amount / total_cost * 100
                if total_cost > 0
                else 0
            )

            output.db_set(
                "rate",
                rate,
            )

            output.db_set(
                "amount",
                total_amount,
            )

            output.db_set(
                "cost_allocation_percentage",
                percentage,
            )

    # =========================================================
    # Manual
    # =========================================================

    @staticmethod
    def _allocate_manually(
        outputs,
        total_cost,
    ):
        """
        التوزيع اليدوي.

        يجب أن يكون مجموع النسب = 100%.
        """

        total_pct = flt(
            sum(
                flt(o.cost_allocation_percentage)
                for o in outputs
            )
        )

        if total_pct <= 0:
            frappe.throw(
                _("Please enter cost allocation percentages")
            )

        if abs(total_pct - 100) > 0.01:
            frappe.throw(
                _(
                    "Cost allocation percentages must sum to 100%%. "
                    "Current: {0}%%"
                ).format(total_pct)
            )

        for output in outputs:

            ratio = flt(
                output.cost_allocation_percentage / 100
            )

            amount = flt(
                total_cost * ratio
            )

            qty = flt(
                output.actual_qty
            )

            rate = (
                amount / qty
                if qty > 0
                else 0
            )

            output.db_set(
                "amount",
                amount,
            )

            output.db_set(
                "rate",
                rate,
            )


# =============================================================
# Selling Price Resolution
# =============================================================

def get_output_selling_price(output):
    """
    الحصول على سعر البيع الحقيقي للمخرج.

    ترتيب البحث:

    1. Item Price إذا كان ERPNext Item موجودًا.
    2. حقول سعر البيع في Coffee Grade Master إذا كانت موجودة.
    3. سعر بيع محفوظ للمخرج نفسه إذا أضيف لاحقًا.

    مهم:
    لا نستخدم:
        price = 1
    ولا:
        valuation_rate * 1.5

    لأن ذلك يعطي تكلفة غير صحيحة.
    """

    item_code = (
        output.item_code
        or ""
    )

    # ---------------------------------------------------------
    # 1. ERPNext Item Price
    # ---------------------------------------------------------

    if item_code and frappe.db.exists(
        "Item",
        item_code,
    ):

        price = frappe.db.get_value(
            "Item Price",
            {
                "item_code": item_code,
                "selling": 1,
            },
            "price_list_rate",
            order_by="valid_from desc",
        )

        price = flt(price)

        if price > 0:
            return price

    # ---------------------------------------------------------
    # 2. Coffee Grade Master
    #
    # نبحث فقط إذا كانت الحقول موجودة فعلاً.
    # هذا يجعل التطبيق متوافقًا مع النسخة الحالية
    # دون افتراض وجود حقل غير موجود.
    # ---------------------------------------------------------

    grade = (
        output.coffee_grade
        or ""
    )

    if grade and frappe.db.exists(
        "DocType",
        "Coffee Grade Master",
    ):

        meta = frappe.get_meta(
            "Coffee Grade Master"
        )

        candidate_fields = [
            "selling_price",
            "sales_price",
            "selling_rate",
            "sales_rate",
            "price",
            "rate",
        ]

        existing_fields = {
            f.fieldname
            for f in meta.fields
        }

        for fieldname in candidate_fields:

            if fieldname not in existing_fields:
                continue

            value = frappe.db.get_value(
                "Coffee Grade Master",
                grade,
                fieldname,
            )

            value = flt(value)

            if value > 0:
                return value

    # ---------------------------------------------------------
    # 3. لا يوجد سعر
    #
    # لا نخمن.
    # ---------------------------------------------------------

    return 0
