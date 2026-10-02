# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt


def validate_grading_outputs(doc, method=None):
    """التحقق من مخرجات عملية Grading"""
    if doc.docstatus != 0 or not doc.operation:
        return

    operation = frappe.get_doc("Coffee Operation Master", doc.operation)
    if not operation.is_grading_operation:
        return

    # يجب أن يكون هناك مخرج واحد على الأقل من نوع Main
    main_outputs = [o for o in doc.outputs if o.output_type == "Main"]
    if not main_outputs:
        frappe.throw(_("Grading operation must have at least one Main output (grade)"))

    # كل مخرج Main يجب أن يكون له coffee_grade و item_code
    for out in main_outputs:
        if not out.coffee_grade:
            frappe.throw(_("Row {0}: Main output in Grading must have a Coffee Grade").format(out.idx))
        if not out.item_code:
            frappe.throw(_("Row {0}: Main output in Grading must have an Item Code").format(out.idx))

    # التحقق من عدم تكرار نفس الدرجة
    grades = [o.coffee_grade for o in main_outputs]
    if len(grades) != len(set(grades)):
        frappe.throw(_("Grading output cannot have duplicate grades"))

    # التحقق من نوع البن
    for out in main_outputs:
        if out.coffee_type not in ["Specialty", "Commercial"]:
            frappe.throw(_("Row {0}: Grading output must be Specialty or Commercial").format(out.idx))
