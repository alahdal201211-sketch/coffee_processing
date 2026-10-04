# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document


class CoffeeProcessRoute(Document):
    def validate(self):
        if not self.steps:
            frappe.throw(_("At least one step is required"))
        sequences = [s.sequence for s in self.steps]
        if len(sequences) != len(set(sequences)):
            frappe.throw(_("Sequence numbers must be unique"))
