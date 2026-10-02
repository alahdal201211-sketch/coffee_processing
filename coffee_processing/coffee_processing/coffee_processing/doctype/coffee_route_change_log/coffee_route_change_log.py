# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document


class CoffeeRouteChangeLog(Document):
    def validate(self):
        if self.coffee_batch and not self.old_route:
            batch = frappe.get_doc("Coffee Batch", self.coffee_batch)
            self.old_route = batch.route
            self.old_step = batch.current_step
            self.old_operation = batch.current_operation
            self.old_warehouse = batch.current_warehouse
            self.old_status = batch.status
            if not self.company:
                self.company = batch.company
            if not self.branch:
                self.branch = batch.branch
