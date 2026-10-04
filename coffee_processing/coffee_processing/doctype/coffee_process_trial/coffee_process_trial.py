import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, flt

class CoffeeProcessTrial(Document):
    def validate(self):
        if not self.steps:
            frappe.throw(_("يجب إضافة خطوة واحدة على الأقل للتجربة."))
        seq=[int(r.sequence or 0) for r in self.steps]
        if any(x<=0 for x in seq) or len(seq)!=len(set(seq)):
            frappe.throw(_("تسلسل خطوات التجربة يجب أن يكون موجبًا وفريدًا."))
        operations={r.operation for r in self.steps}
        if len(operations) != len(self.steps):
            frappe.throw(_("لا يمكن تكرار العملية داخل خطوات التجربة بنفس المسار."))

    def on_submit(self):
        self.db_set("status","Submitted")

    @frappe.whitelist()
    def approve_trial(self):
        if self.docstatus != 1:
            frappe.throw(_("يجب اعتماد التجربة بعد إرسالها."))
        self.db_set("status","Approved")
        self.db_set("approved_by",frappe.session.user)
        self.db_set("approval_date",now())
        return self.name

    @frappe.whitelist()
    def create_production_plan(self, planned_qty):
        """Create a scalable production plan from an approved trial.

        Trial data remains non-stock-affecting. The resulting plan is the
        bridge to real production orders.
        """
        if self.status != "Approved":
            frappe.throw(_("لا يمكن إنشاء خطة إنتاج إلا من تجربة معتمدة."))
        planned_qty = flt(planned_qty)
        if planned_qty <= 0:
            frappe.throw(_("الكمية المخططة يجب أن تكون أكبر من صفر."))
        if self.production_plan and frappe.db.exists("Coffee Production Plan", self.production_plan):
            return self.production_plan
        plan = frappe.new_doc("Coffee Production Plan")
        plan.plan_name = _("خطة إنتاج من التجربة {0}").format(self.trial_name)
        plan.trial = self.name
        plan.company = self.company
        plan.branch = self.branch
        plan.reference_batch = self.reference_batch
        plan.planned_qty = planned_qty
        trial_base_qty = flt(self.trial_qty)
        if trial_base_qty <= 0:
            frappe.throw(_("كمية التجربة يجب أن تكون أكبر من صفر."))
        plan.scale_factor = planned_qty / trial_base_qty
        plan.status = "Draft"
        for row in sorted(self.steps, key=lambda x: int(x.sequence or 0)):
            step = plan.append("steps", {})
            step.sequence = row.sequence
            step.operation = row.operation
            step.planned_qty = planned_qty
            step.duration_hours = row.duration_hours
            step.temperature = row.temperature
            step.moisture_target = row.moisture_target
            step.notes = row.notes
        plan.insert(ignore_permissions=True)
        self.db_set("production_plan", plan.name)
        return plan.name
