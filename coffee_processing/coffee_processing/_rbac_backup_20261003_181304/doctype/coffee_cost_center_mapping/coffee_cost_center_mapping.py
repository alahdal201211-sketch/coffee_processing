# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document


class CoffeeCostCenterMapping(Document):
    def validate(self):
        filters = {
            "operation": self.operation,
            "company": self.company,
            "name": ["!=", self.name]
        }
        if self.branch:
            filters["branch"] = self.branch
        if frappe.db.exists("Coffee Cost Center Mapping", filters):
            frappe.throw(_("Cost Center Mapping already exists for operation {0}, company {1}").format(
                self.operation, self.company))
