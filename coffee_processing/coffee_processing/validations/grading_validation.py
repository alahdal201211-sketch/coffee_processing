# -*- coding: utf-8 -*-
import frappe
from frappe import _


def _grade_for_item(item):
    if not item:
        return None
    return frappe.db.get_value(
        "Coffee Grade Master",
        {"active": 1, "specialty_item_code": item},
        "name",
    ) or frappe.db.get_value(
        "Coffee Grade Master",
        {"active": 1, "commercial_item_code": item},
        "name",
    )


def validate_grading_outputs(doc, method=None):
    """Validate grading outputs without hardcoding grade numbers.

    The current output child uses ``item``/``output_type``. Grade is resolved
    dynamically from Coffee Grade Master by the output item.
    """
    if doc.docstatus != 0 or not doc.operation:
        return
    operation = frappe.get_doc("Coffee Operation Master", doc.operation)
    if not operation.is_grading_operation:
        return

    main_outputs = [o for o in doc.outputs if o.output_type in ("Main", "Main Product")]
    if not main_outputs:
        frappe.throw(_("يجب أن يحتوي التصنيف على مخرج رئيسي واحد على الأقل."))

    grades=[]
    for out in main_outputs:
        if not out.item:
            frappe.throw(_("المخرج الرئيسي في التصنيف يجب أن يحتوي على الصنف."))
        grade = getattr(out, "coffee_grade", None) or _grade_for_item(out.item)
        if not grade:
            frappe.throw(_("الصنف {0} ليس مرتبطًا بدرجة نشطة في Coffee Grade Master.").format(out.item))
        grades.append(grade)

    if len(grades) != len(set(grades)):
        frappe.throw(_("لا يمكن تكرار نفس الدرجة في مخرجات التصنيف."))
