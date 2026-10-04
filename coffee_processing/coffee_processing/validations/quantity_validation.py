# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt


def validate_available_quantity(doc, method=None):
    if doc.docstatus != 0 or not doc.coffee_batch:
        return
    batch = frappe.get_doc("Coffee Batch", doc.coffee_batch)
    free = flt(batch.qty) - flt(batch.reserved_qty)

    total_planned = sum(flt(i.planned_qty) for i in doc.inputs)
    total_actual = sum(flt(i.actual_qty) for i in doc.inputs)

    if total_planned > free + 0.01:
        frappe.throw(_("Insufficient quantity in batch {0}. Available: {1}, Requested: {2}").format(
            batch.name, free, total_planned))
    if total_actual > free + 0.01:
        frappe.throw(_("Insufficient quantity in batch {0}. Available: {1}, Requested: {2}").format(
            batch.name, free, total_actual))


def validate_input_quantity(doc, method=None):
    if doc.docstatus != 0:
        return
    for inp in doc.inputs:
        if flt(inp.planned_qty) <= 0:
            frappe.throw(_("Input quantity must be greater than zero"))
        if flt(inp.actual_qty) < 0:
            frappe.throw(_("Actual input quantity cannot be negative"))


def validate_output_quantity(doc, method=None):
    if doc.docstatus != 0:
        return
    for out in doc.outputs:
        if flt(out.planned_qty) < 0:
            frappe.throw(_("Planned output quantity cannot be negative"))
        if flt(out.actual_qty) < 0:
            frappe.throw(_("Actual output quantity cannot be negative"))


def validate_multiple_inputs(doc, method=None):
    if doc.docstatus != 0 or not doc.operation:
        return
    operation = frappe.get_doc("Coffee Operation Master", doc.operation)
    if len(doc.inputs) > 1 and not operation.allow_multiple_inputs:
        frappe.throw(_("Operation {0} does not allow multiple inputs").format(doc.operation))


def validate_multiple_outputs(doc, method=None):
    if doc.docstatus != 0 or not doc.operation:
        return
    operation = frappe.get_doc("Coffee Operation Master", doc.operation)
    if len(doc.outputs) > 1 and not operation.allow_multiple_outputs:
        frappe.throw(_("Operation {0} does not allow multiple outputs").format(doc.operation))


def validate_partial_processing(doc, method=None):
    if doc.docstatus != 0 or not doc.operation:
        return
    operation = frappe.get_doc("Coffee Operation Master", doc.operation)
    if not operation.allow_partial_quantity:
        batch = frappe.get_doc("Coffee Batch", doc.coffee_batch)
        available = flt(batch.qty)
        total_planned = sum(flt(i.planned_qty) for i in doc.inputs)
        if abs(total_planned - available) > 0.01:
            frappe.throw(_("Operation {0} does not allow partial processing.").format(doc.operation))
