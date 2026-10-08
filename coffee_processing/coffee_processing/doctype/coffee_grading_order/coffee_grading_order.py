import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

class CoffeeGradingOrder(Document):
    def validate(self):
        from coffee_processing.coffee_processing.services.stage_processing_service import validate_common
        validate_common(self, "GRADING")
        for r in self.outputs:
            grade = getattr(r, "coffee_grade", None) or self.target_grade
            if not grade:
                frappe.throw(_("يجب تحديد درجة لكل مخرج في عملية التصنيف."))
            r.coffee_grade = grade
        self.quality_result = self.quality_result or "Approved"
        self.sample_reference = self.sample_reference or self.target_grade or self.name

    def before_submit(self):
        from coffee_processing.coffee_processing.services.stage_processing_service import create_process_order
        cpo = create_process_order(self, "GRADING")
        self.process_order = cpo.name
        self.stock_entry = cpo.stock_entry

    def on_submit(self):
        self.db_set("status", "Completed")

    def on_cancel(self):
        if self.process_order:
            cpo=frappe.get_doc("Coffee Process Order",self.process_order)
            if cpo.docstatus==1: cpo.cancel()
        self.db_set("status","Cancelled")
