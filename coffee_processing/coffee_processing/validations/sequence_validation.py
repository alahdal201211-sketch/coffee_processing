# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
from coffee_processing.coffee_processing.services.sequence_service import (
    get_allowed_operations, validate_sequence,
)


def validate_processing_sequence(doc, method=None):
    if doc.docstatus != 0 or not doc.coffee_batch or not doc.operation:
        return
    batch = frappe.get_doc("Coffee Batch", doc.coffee_batch)
    if batch.status in ["Completed", "Sold", "Rejected", "Consumed"]:
        frappe.throw(_("Cannot process batch {0} with status {1}").format(batch.name, batch.status))
    result = validate_sequence(batch, doc.operation)
    if not result["valid"]:
        frappe.throw(result["message"])
    if result["next_step"]:
        doc.route_step = result["next_step"].name
        doc.sequence = result["next_step"].sequence


def validate_batch_operation(doc, method=None):
    if doc.docstatus != 0 or not doc.coffee_batch or not doc.operation:
        return
    batch = frappe.get_doc("Coffee Batch", doc.coffee_batch)
    allowed = get_allowed_operations(batch)
    if not allowed:
        frappe.throw(_("Batch {0} has completed all processing steps").format(batch.name))
    if doc.operation not in allowed:
        frappe.throw(_("Operation {0} is not allowed for batch {1}.").format(doc.operation, batch.name))
