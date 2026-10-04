import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

class CoffeeSortingOrder(Document):

    def validate(self):
        if not self.inputs:
            frappe.throw(_("يجب إضافة دفعة إدخال واحدة على الأقل."))

        if self.outputs:
            self.input_qty_total = sum(flt(r.qty) for r in self.inputs)
            self.output_qty_total = sum(flt(r.qty) for r in self.outputs)

            self.loss_qty = max(
                flt(self.input_qty_total) - flt(self.output_qty_total),
                0
            )

            if self.input_qty_total:
                self.yield_percent = (
                    flt(self.output_qty_total)
                    / flt(self.input_qty_total)
                    * 100
                )

        self.direct_cost = sum(
            flt(r.amount) for r in self.costs
        )

        self.total_cost = (
            flt(self.direct_cost)
            + flt(self.overhead_cost)
        )

        if self.output_qty_total:
            self.cost_per_kg = (
                flt(self.total_cost)
                / flt(self.output_qty_total)
            )

    def on_submit(self):
        self.db_set("status", "Completed")
