import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

class CoffeeDryingOrder(Document):
    def validate(self):
        from coffee_processing.coffee_processing.services.stage_processing_service import validate_common
        validate_common(self, "DRYING", 25, 30)

    def before_submit(self):
        from coffee_processing.coffee_processing.services.stage_processing_service import create_process_order, allocate_resources
        # Resource capacity is reserved before the central stock transaction.
        allocate_resources(self, "Drying Bed", "Coffee Drying Bed", self.target_warehouse or self.source_warehouse, 50)
        cpo=create_process_order(self, "DRYING", 25, 30)
        for a in self.resource_allocations:
            if a.storage_unit:
                frappe.db.set_value("Coffee Storage Unit",a.storage_unit,"current_process_order",cpo.name)
        self.process_order=cpo.name
        self.stock_entry=cpo.stock_entry

    def on_submit(self):
        from coffee_processing.coffee_processing.services.stage_processing_service import release_resources
        release_resources(self, "Coffee Drying Bed")
        self.db_set("status","Completed")

    def on_cancel(self):
        if self.process_order:
            cpo=frappe.get_doc("Coffee Process Order",self.process_order)
            if cpo.docstatus==1: cpo.cancel()
        from coffee_processing.coffee_processing.services.stage_processing_service import release_resources
        release_resources(self, "Coffee Drying Bed")
        self.db_set("status","Cancelled")
