# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document


class CoffeeSample(Document):
    def validate(self):
        if self.coffee_batch:
            batch = frappe.get_doc("Coffee Batch", self.coffee_batch)
            if not self.coffee_type:
                self.coffee_type = batch.coffee_type
            if not self.coffee_grade:
                self.coffee_grade = batch.coffee_grade
            if not self.warehouse:
                self.warehouse = batch.current_warehouse
            if not self.company:
                self.company = batch.company
            if not self.branch:
                self.branch = batch.branch

    def on_submit(self):
        self.db_set("status", "Submitted")


def validate(doc, method=None):
    doc.validate()


def on_submit(doc, method=None):
    doc.on_submit()
