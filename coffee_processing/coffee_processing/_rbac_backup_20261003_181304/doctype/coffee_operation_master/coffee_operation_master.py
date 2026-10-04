# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document


class CoffeeOperationMaster(Document):
    def validate(self):
        if self.operation_code:
            self.operation_code = self.operation_code.upper().strip()

        if self.operation_code == "GRADING":
            self.is_grading_operation = 1
            self.allow_multiple_outputs = 1
            self.cost_allocation_method = "Hybrid"
