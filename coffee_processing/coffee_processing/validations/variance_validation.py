# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt


def validate_and_calculate_variance(doc, method=None):
    if doc.docstatus != 0:
        return

    total_input = sum(flt(i.actual_qty) for i in doc.inputs)
    physical_output = sum(flt(o.actual_qty) for o in doc.outputs if o.output_type != "Loss")
    recorded_loss = sum(flt(o.actual_qty) for o in doc.outputs if o.output_type == "Loss")
    variance = total_input - physical_output - recorded_loss

    doc.total_input_qty = total_input
    doc.total_output_qty = physical_output
    doc.total_loss_qty = recorded_loss
    doc.variance = variance

    if abs(variance) < 0.01:
        doc.variance_type = "None"
    elif variance > 0:
        doc.variance_type = "Shortage"
    else:
        doc.variance_type = "Gain"

    if not doc.operation:
        return

    operation = frappe.get_doc("Coffee Operation Master", doc.operation)
    if abs(variance) > 0.01:
        if not operation.allow_variance:
            frappe.throw(_("Variance of {0} KG is not allowed for operation {1}.").format(
                abs(variance), doc.operation))
        if variance < 0 and not operation.allow_negative_variance:
            frappe.throw(_("Negative variance (Gain) of {0} KG is not allowed for operation {1}").format(
                abs(variance), doc.operation))
        if not doc.variance_reason:
            frappe.throw(_("Variance of {0} KG detected. Please provide a reason.").format(abs(variance)))

    if operation.variance_requires_approval:
        threshold = flt(operation.variance_threshold) or 5
        if abs(variance) > threshold and not doc.variance_approved_by:
            frappe.throw(_("Variance of {0} KG exceeds threshold ({1} KG). Manager approval required.").format(
                abs(variance), threshold))


def validate_loss_policy(doc, method=None):
    if doc.docstatus != 0 or not doc.operation:
        return
    operation = frappe.get_doc("Coffee Operation Master", doc.operation)
    total_loss = sum(flt(o.actual_qty) for o in doc.outputs if o.output_type == "Loss")
    if total_loss > 0 and not operation.allow_loss:
        frappe.throw(_("Loss of {0} KG is not allowed for operation {1}").format(
            total_loss, doc.operation))
