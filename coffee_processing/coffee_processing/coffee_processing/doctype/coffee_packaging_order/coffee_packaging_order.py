# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CoffeePackagingOrder(Document):
    def validate(self):
        self.validate_packaging()
        self.calculate_totals()

    def validate_packaging(self):
        if flt(self.number_of_packages) <= 0:
            frappe.throw(_("Number of packages must be greater than zero"))
        if flt(self.package_size) <= 0:
            frappe.throw(_("Package size must be greater than zero"))

    def calculate_totals(self):
        self.output_qty = flt(self.number_of_packages) * flt(self.package_size)
        self.total_cost = (
            flt(self.material_cost) + flt(self.labor_cost) +
            flt(self.machine_cost) + flt(self.other_cost)
        )
        if self.output_qty > 0:
            self.output_cost_per_kg = self.total_cost / self.output_qty

    def on_submit(self):
        self.db_set("status", "Completed")
        self.db_set("completed_by", frappe.session.user)


def validate(doc, method=None):
    doc.validate()


def on_submit(doc, method=None):
    doc.on_submit()
