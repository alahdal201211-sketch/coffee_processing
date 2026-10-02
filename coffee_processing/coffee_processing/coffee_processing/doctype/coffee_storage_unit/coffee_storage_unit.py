import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

class CoffeeStorageUnit(Document):
    def validate(self):
        if flt(self.capacity_kg) <= 0:
            frappe.throw(_("سعة وحدة التخزين يجب أن تكون أكبر من صفر."))
        if self.current_qty is None:
            self.current_qty = 0
        if flt(self.current_qty) > flt(self.capacity_kg) + 0.000001:
            frappe.throw(_("الكمية الحالية تتجاوز سعة وحدة التخزين."))
        if self.storage_type == "Fermentation Barrel" and flt(self.capacity_kg) != 160:
            frappe.throw(_("سعة برميل التخمير القياسية يجب أن تكون 160 كجم."))
        if self.storage_type == "Drying Bed" and flt(self.capacity_kg) != 50:
            frappe.throw(_("سعة سرير التجفيف القياسية يجب أن تكون 50 كجم."))
