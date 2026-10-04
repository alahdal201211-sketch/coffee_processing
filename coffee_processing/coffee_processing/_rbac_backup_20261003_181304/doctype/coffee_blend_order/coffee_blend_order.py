# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now


class CoffeeBlendOrder(Document):
    def validate(self):
        self.validate_sources()
        self.calculate_totals()

    def validate_sources(self):
        if len(self.sources) < 2:
            frappe.throw(_("Blend must have at least two sources"))
        total_qty = sum(flt(s.qty) for s in self.sources)
        if abs(total_qty - flt(self.total_qty)) > 0.01:
            frappe.throw(_("Blend source quantities do not match total quantity"))

    def calculate_totals(self):
        total_qty = sum(flt(s.qty) for s in self.sources)
        total_amount = sum(flt(s.qty) * flt(s.rate or 0) for s in self.sources)
        for s in self.sources:
            s.amount = flt(s.qty) * flt(s.rate or 0)
            s.percentage = (flt(s.qty) / total_qty * 100) if total_qty else 0
        self.actual_cost = total_amount
        self.cost_per_kg = total_amount / total_qty if total_qty else 0

    def on_submit(self):
        self.db_set("status", "Approved")
        self.db_set("approved_by", frappe.session.user)
        self.db_set("approval_date", now())


def validate(doc, method=None):
    doc.validate()


def on_submit(doc, method=None):
    doc.on_submit()
