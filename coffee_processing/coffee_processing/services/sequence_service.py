# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _


def get_next_executable_step(batch):
    if isinstance(batch, str):
        batch = frappe.get_doc("Coffee Batch", batch)
    if not batch.route:
        return None
    route = frappe.get_doc("Coffee Process Route", batch.route)
    current_seq = batch.current_step or 0
    for step in sorted(route.steps, key=lambda x: x.sequence):
        if step.sequence <= current_seq:
            continue
        if step.required:
            return step
        if step.allow_skip_if_optional:
            continue
        return step
    return None


def get_allowed_operations(batch):
    if isinstance(batch, str):
        batch = frappe.get_doc("Coffee Batch", batch)
    next_step = get_next_executable_step(batch)
    if not next_step:
        return []
    operations = [next_step.operation]
    route = frappe.get_doc("Coffee Process Route", batch.route)
    current_seq = batch.current_step or 0
    for step in sorted(route.steps, key=lambda x: x.sequence):
        if step.sequence <= current_seq:
            continue
        if step.required:
            if step.operation not in operations:
                operations.append(step.operation)
            break
    return operations


def is_batch_completed(batch):
    return get_next_executable_step(batch) is None


def advance_batch_step(batch, operation=None):
    if isinstance(batch, str):
        batch = frappe.get_doc("Coffee Batch", batch)
    next_step = get_next_executable_step(batch)
    if next_step:
        batch.db_set("current_step", next_step.sequence)
        batch.db_set("current_operation", next_step.operation)
        batch.db_set("status", "Ready for Processing")
    else:
        batch.db_set("status", "Completed")
    return True


def validate_sequence(batch, operation):
    if isinstance(batch, str):
        batch = frappe.get_doc("Coffee Batch", batch)
    if not batch.route:
        return {"valid": False, "message": _("Batch has no route assigned"), "next_step": None}
    allowed = get_allowed_operations(batch)
    if not allowed:
        return {
            "valid": False,
            "message": _("Batch {0} has completed all processing steps").format(batch.name),
            "next_step": None,
        }
    if operation not in allowed:
        next_step = get_next_executable_step(batch)
        return {
            "valid": False,
            "message": _(
                "Cannot execute operation {0} for batch {1}. Current step: {2}. Next allowed operation: {3}"
            ).format(operation, batch.name, batch.current_step,
                     next_step.operation if next_step else "None"),
            "next_step": next_step,
        }
    return {"valid": True, "message": "", "next_step": get_next_executable_step(batch)}
