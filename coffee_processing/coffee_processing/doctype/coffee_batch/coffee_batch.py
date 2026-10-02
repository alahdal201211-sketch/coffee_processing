# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CoffeeBatch(Document):
    def validate(self):
        self.validate_route()
        self.set_grade_batch_flag()
        self.set_custom_item_code()
        self.calculate_totals()

    def set_grade_batch_flag(self):
        self.is_grade_batch = 1 if self.coffee_grade else 0

    def set_custom_item_code(self):
        """توليد كود الصنف تلقائياً إذا لم يكن موجوداً"""
        if self.custom_item_code:
            return

        if self.coffee_grade and self.coffee_type in ["Specialty", "Commercial"]:
            grade = frappe.get_doc("Coffee Grade Master", self.coffee_grade)
            if self.coffee_type == "Specialty" and grade.specialty_item_code:
                self.custom_item_code = grade.specialty_item_code
            elif self.coffee_type == "Commercial" and grade.commercial_item_code:
                self.custom_item_code = grade.commercial_item_code
        elif self.coffee_type:
            # توليد كود افتراضي
            self.custom_item_code = f"{self.coffee_type.upper()}-{self.name or 'NEW'}"

    def validate_route(self):
        if self.route:
            route = frappe.get_doc("Coffee Process Route", self.route)
            if not route.active:
                frappe.throw(_("Route {0} is not active").format(self.route))
            if self.company and route.company != self.company:
                frappe.throw(_("Route {0} does not belong to company {1}").format(
                    self.route, self.company))

    def calculate_totals(self):
        """حساب التكلفة الإجمالية لكل كجم"""
        qty = flt(self.qty) or 0
        rate = flt(self.valuation_rate) or 0
        self.total_value = qty * rate
        self.cost_per_kg = rate

    @property
    def available_qty(self):
        return (flt(self.qty) or 0) - (flt(self.reserved_qty) or 0)

    def add_qty(self, qty, rate=None):
        """إضافة كمية مع حساب المتوسط المرجح"""
        current_qty = flt(self.qty) or 0
        current_value = current_qty * flt(self.valuation_rate or 0)
        new_value = flt(qty) * flt(rate or self.valuation_rate or 0)
        new_qty = current_qty + flt(qty)

        if new_qty > 0:
            self.valuation_rate = (current_value + new_value) / new_qty
        self.qty = new_qty
        self.calculate_totals()

    def reduce_qty(self, qty):
        """تقليل كمية"""
        self.qty = max(0, (flt(self.qty) or 0) - flt(qty))
        self.calculate_totals()


def validate(doc, method=None):
    doc.validate()
