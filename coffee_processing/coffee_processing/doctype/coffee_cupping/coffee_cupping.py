# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import flt


class CoffeeCupping(Document):
    def validate(self):
        self.calculate_total_score()
        if self.coffee_sample:
            sample = frappe.get_doc("Coffee Sample", self.coffee_sample)
            self.coffee_batch = sample.coffee_batch
            self.coffee_grade = sample.coffee_grade
            if not self.company:
                self.company = sample.company
            if not self.branch:
                self.branch = sample.branch

    def calculate_total_score(self):
        score_fields = ["aroma", "flavor", "acidity", "body",
                        "aftertaste", "balance", "sweetness", "clean_cup"]
        total = sum(flt(getattr(self, f, 0)) for f in score_fields)
        self.total_score = total
        self.final_score = total - flt(self.defect_score or 0)

        if self.final_score >= 85:
            self.cupping_result = "Specialty"
        elif self.final_score >= 80:
            self.cupping_result = "Premium"
        elif self.final_score >= 70:
            self.cupping_result = "Commercial"
        else:
            self.cupping_result = "Rejected"

    def on_submit(self):
        self.db_set("status", "Submitted")
        if self.coffee_sample:
            sample = frappe.get_doc("Coffee Sample", self.coffee_sample)
            sample.db_set("cupping_status", "Cupped")
            sample.db_set("coffee_cupping", self.name)
            if self.cupping_result in ["Specialty", "Premium", "Commercial"]:
                sample.db_set("quality_status", "Approved")
                sample.db_set("status", "Approved")
            else:
                sample.db_set("quality_status", "Rejected")
                sample.db_set("status", "Rejected")


def validate(doc, method=None):
    doc.validate()


def on_submit(doc, method=None):
    doc.on_submit()
