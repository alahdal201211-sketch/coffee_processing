# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _


def validate_operation_permission(doc, method=None):
    if doc.docstatus != 0 or not doc.operation:
        return
    operation = frappe.get_doc("Coffee Operation Master", doc.operation)

    if operation.require_assignment and doc.assigned_user:
        if doc.assigned_user != frappe.session.user:
            if "Coffee Manager" not in frappe.get_roles(frappe.session.user):
                frappe.throw(_("Operation {0} is assigned to {1}. You are not authorized.").format(
                    doc.operation, doc.assigned_user))

    if operation.required_role:
        if operation.required_role not in frappe.get_roles(frappe.session.user):
            if "Coffee Manager" not in frappe.get_roles(frappe.session.user):
                frappe.throw(_("User {0} does not have the required role: {1}").format(
                    frappe.session.user, operation.required_role))


def validate_approval_permission(user=None):
    user = user or frappe.session.user
    roles = frappe.get_roles(user)
    if "Coffee Manager" not in roles and "System Manager" not in roles:
        frappe.throw(_("User {0} is not authorized to approve").format(user))


def validate_costing_permission(user=None):
    user = user or frappe.session.user
    roles = frappe.get_roles(user)
    if "Coffee Manager" not in roles and "Coffee Accountant" not in roles:
        frappe.throw(_("User {0} is not authorized to modify costs").format(user))
