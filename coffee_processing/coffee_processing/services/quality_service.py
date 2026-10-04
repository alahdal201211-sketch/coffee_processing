# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, now, nowdate


def create_sample(batch_name, sample_type, sample_qty, warehouse=None, notes=None):
    batch = frappe.get_doc("Coffee Batch", batch_name)
    available = flt(batch.qty) - flt(batch.reserved_qty)
    if flt(sample_qty) > available:
        frappe.throw(_("Sample quantity {0} exceeds available quantity {1} in batch {2}").format(
            sample_qty, available, batch.name))

    sample = frappe.new_doc("Coffee Sample")
    sample.coffee_batch = batch_name
    sample.coffee_type = batch.coffee_type
    sample.coffee_grade = batch.coffee_grade
    sample.sample_type = sample_type
    sample.sample_qty = flt(sample_qty)
    sample.warehouse = warehouse or batch.current_warehouse
    sample.status = "Draft"
    sample.taken_by = frappe.session.user
    sample.taken_time = now()
    sample.notes = notes
    sample.company = batch.company
    sample.branch = batch.branch
    sample.insert()
    return sample


def create_cupping(sample_name, cupping_data):
    sample = frappe.get_doc("Coffee Sample", sample_name)
    if sample.status not in ["Submitted", "Cupped"]:
        frappe.throw(_("Sample {0} must be submitted before cupping").format(sample.sample_no))

    cupping = frappe.new_doc("Coffee Cupping")
    cupping.coffee_sample = sample_name
    cupping.coffee_batch = sample.coffee_batch
    cupping.coffee_grade = sample.coffee_grade
    cupping.cupping_date = nowdate()
    cupping.status = "Draft"
    cupping.cupped_by = frappe.session.user
    cupping.cupping_time = now()
    cupping.company = sample.company
    cupping.branch = sample.branch

    for field in ["aroma", "flavor", "acidity", "body", "aftertaste",
                  "balance", "sweetness", "clean_cup", "defect_score"]:
        if field in cupping_data:
            setattr(cupping, field, flt(cupping_data[field]))

    for field in ["flavor_notes", "notes", "cupping_location", "session_no"]:
        if field in cupping_data:
            setattr(cupping, field, cupping_data[field])

    cupping.calculate_total_score()
    cupping.insert()
    return cupping


def can_proceed_to_packaging(batch_name):
    batch = frappe.get_doc("Coffee Batch", batch_name)
    if batch.coffee_type not in ["Specialty", "Commercial", "Mixed"]:
        return {"allowed": False, "reason": _("Cannot package {0} batches").format(batch.coffee_type)}
    if batch.quality_status != "Approved":
        return {"allowed": False, "reason": _("Batch {0} must be quality approved before packaging").format(batch.name)}
    if batch.cupping_status not in ["Cupped", "Approved", "Not Required"]:
        return {"allowed": False, "reason": _("Batch {0} must be cupped before packaging").format(batch.name)}
    available = flt(batch.qty) - flt(batch.reserved_qty)
    if available <= 0:
        return {"allowed": False, "reason": _("Batch {0} has no available quantity").format(batch.name)}
    return {"allowed": True, "reason": ""}


def get_batch_quality_status(batch_name):
    batch = frappe.get_doc("Coffee Batch", batch_name)
    last_sample = frappe.get_all(
        "Coffee Sample",
        filters={"coffee_batch": batch_name, "docstatus": 1},
        fields=["name", "sample_no", "sample_type", "sample_date", "status"],
        order_by="creation desc", limit=1,
    )
    last_cupping = frappe.get_all(
        "Coffee Cupping",
        filters={"coffee_batch": batch_name, "docstatus": 1},
        fields=["name", "cupping_no", "total_score", "final_score",
                "cupping_result", "cupping_date"],
        order_by="creation desc", limit=1,
    )
    return {
        "batch": batch.name,
        "quality_status": batch.quality_status,
        "cupping_status": batch.cupping_status,
        "last_sample": last_sample[0] if last_sample else None,
        "last_cupping": last_cupping[0] if last_cupping else None,
    }


def approve_quality(batch_name, approved_by=None):
    batch = frappe.get_doc("Coffee Batch", batch_name)
    batch.quality_status = "Approved"
    batch.save()
    return batch


def reject_quality(batch_name, reason, rejected_by=None):
    batch = frappe.get_doc("Coffee Batch", batch_name)
    batch.quality_status = "Rejected"
    batch.status = "Rejected"
    batch.notes = (batch.notes or "") + f"\n\n[Rejected] {reason}"
    batch.save()
    return batch


def check_pending_quality_notifications():
    batches = frappe.get_all(
        "Coffee Batch",
        filters={"status": "Ready for Processing", "quality_status": "Pending"},
        fields=["name"]
    )
    for b in batches:
        frappe.publish_realtime(event="coffee_quality_pending", message={"batch": b.name})


def check_pending_cupping_notifications():
    samples = frappe.get_all(
        "Coffee Sample",
        filters={"status": "Submitted", "cupping_status": "Pending"},
        fields=["name", "sample_no"]
    )
    for s in samples:
        frappe.publish_realtime(event="coffee_cupping_pending", message={"sample": s.name})


def get_cost_center_mapping(operation, company=None, branch=None):
    company = company or frappe.defaults.get_user_default("Company")
    filters = {"operation": operation, "company": company, "active": 1}
    if branch:
        filters["branch"] = branch
    return frappe.db.get_value(
        "Coffee Cost Center Mapping",
        filters,
        ["cost_center", "wip_account", "expense_account"],
        as_dict=True
    )
