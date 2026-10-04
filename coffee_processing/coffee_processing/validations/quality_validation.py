# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt
from coffee_processing.coffee_processing.services.quality_service import can_proceed_to_packaging


def validate_quality_requirements(doc, method=None):
    if doc.docstatus != 0 or not doc.operation:
        return
    operation = frappe.get_doc("Coffee Operation Master", doc.operation)
    batch = frappe.get_doc("Coffee Batch", doc.coffee_batch)

    if operation.requires_sample:
        samples = frappe.get_all("Coffee Sample", filters={
            "coffee_batch": doc.coffee_batch, "docstatus": 1
        })
        if not samples:
            frappe.throw(_("Operation {0} requires a sample. Please create a sample first.").format(
                doc.operation))

    if operation.requires_quality and batch.quality_status == "Pending":
        frappe.throw(_("Operation {0} requires quality inspection for batch {1}").format(
            doc.operation, batch.name))


def validate_cupping_scores(doc, method=None):
    if doc.docstatus != 0:
        return
    for field in ["aroma", "flavor", "acidity", "body", "aftertaste",
                  "balance", "sweetness", "clean_cup", "defect_score"]:
        value = flt(getattr(doc, field, 0))
        if value < 0 or value > 10:
            frappe.throw(_("{0} must be between {1} and {2}").format(
                field.replace("_", " ").title(), 0, 10))
    if doc.total_score and (doc.total_score < 0 or doc.total_score > 100):
        frappe.throw(_("Total score must be between 0 and 100"))


def validate_packaging_quality(doc, method=None):
    if doc.docstatus != 0 or not doc.coffee_batch:
        return
    result = can_proceed_to_packaging(doc.coffee_batch)
    if not result["allowed"]:
        frappe.throw(result["reason"])


def validate_sample_quantity(doc, method=None):
    if doc.docstatus != 0 or not doc.coffee_batch:
        return
    batch = frappe.get_doc("Coffee Batch", doc.coffee_batch)
    available = flt(batch.qty) - flt(batch.reserved_qty)
    if flt(doc.sample_qty) > available:
        frappe.throw(_("Sample quantity {0} exceeds available quantity {1} in batch {2}").format(
            doc.sample_qty, available, batch.name))
