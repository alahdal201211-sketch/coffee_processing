# -*- coding: utf-8 -*-
import frappe

def execute():
    for role_name in ["Coffee Manager", "Coffee Processing User", "Coffee Packaging User", "Coffee Accountant"]:
        if not frappe.db.exists("Role", role_name):
            role = frappe.new_doc("Role")
            role.role_name = role_name
            role.insert(ignore_permissions=True)
