# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from coffee_processing.coffee_processing.services.stock_service import create_repack_stock_entry

class CoffeePackagingOrder(Document):
    def validate(self):
        if not self.coffee_batch:
            frappe.throw(_("يجب تحديد دفعة البن."))
        if flt(self.input_qty) <= 0:
            frappe.throw(_("الكمية المدخلة يجب أن تكون أكبر من صفر."))
        if flt(self.package_size) <= 0 or flt(self.number_of_packages) <= 0:
            frappe.throw(_("حجم العبوة وعدد العبوات يجب أن يكونا أكبر من صفر."))
        batch=frappe.get_doc("Coffee Batch",self.coffee_batch)
        if flt(self.input_qty)>flt(batch.qty)+0.000001:
            frappe.throw(_("الكمية المدخلة تتجاوز الكمية المتاحة في الدفعة."))
        if not self.source_warehouse: self.source_warehouse=batch.current_warehouse
        if not self.input_item_code: self.input_item_code=batch.custom_item_code or frappe.db.get_value("Batch",batch.erpnext_batch,"item")
        if not self.target_item_code: frappe.throw(_("يجب تحديد صنف المنتج المعبأ."))
        if not self.target_warehouse: frappe.throw(_("يجب تحديد مخزن المنتج المعبأ."))
        self.output_qty=flt(self.number_of_packages)*flt(self.package_size)
        if self.output_qty<=0: frappe.throw(_("كمية الناتج يجب أن تكون أكبر من صفر."))
        if self.output_qty>flt(self.input_qty)+0.000001:
            frappe.throw(_("كمية التعبئة لا يمكن أن تتجاوز الكمية المدخلة."))
        self.total_cost=flt(self.material_cost)+flt(self.labor_cost)+flt(self.machine_cost)+flt(self.other_cost)
        base_cost=flt(batch.cost_per_kg or batch.valuation_rate)
        self.output_cost_per_kg=base_cost+(self.total_cost/self.output_qty if self.output_qty else 0)

    def before_submit(self):
        if self.stock_entry: return
        batch=frappe.get_doc("Coffee Batch",self.coffee_batch)
        rate=flt(batch.cost_per_kg or batch.valuation_rate)+ (flt(self.total_cost)/self.output_qty if self.output_qty else 0)
        inputs=[{"item":self.input_item_code,"qty":self.input_qty,"uom":self.uom or frappe.db.get_value("Item",self.input_item_code,"stock_uom"),"warehouse":self.source_warehouse,"batch_no":batch.erpnext_batch,"rate":flt(batch.cost_per_kg or batch.valuation_rate)}]
        outputs=[{"item":self.target_item_code,"qty":self.output_qty,"uom":frappe.db.get_value("Item",self.target_item_code,"stock_uom"),"warehouse":self.target_warehouse,"rate":rate}]
        se, rows=create_repack_stock_entry(self.company,self.packaging_date,inputs,outputs,"Coffee Packaging "+self.name)
        self.stock_entry=se.name
        out_batch=rows[0][1].batch_no if rows and getattr(rows[0][1],"batch_no",None) else None
        if not out_batch:
            out_batch=frappe.model.naming.make_autoname("CPO-BATCH-.YYYY.-.#####")
        cb=frappe.new_doc("Coffee Batch")
        cb.custom_item_code=self.target_item_code; cb.item_name=frappe.db.get_value("Item",self.target_item_code,"item_name") or self.target_item_code
        cb.company=self.company; cb.branch=self.branch; cb.route=batch.route; cb.current_step=8; cb.current_operation="PACKAGING"; cb.current_warehouse=self.target_warehouse
        cb.qty=self.output_qty; cb.valuation_rate=rate; cb.cost_per_kg=rate; cb.total_value=self.output_qty*rate; cb.source_type="Processing"; cb.parent_batch=batch.name; cb.erpnext_batch=out_batch; cb.status="Completed"; cb.insert(ignore_permissions=True)
        self.output_batch=cb.name
        batch.reduce_qty(self.input_qty); batch.save(ignore_permissions=True)
        self.db_set("stock_entry",se.name,update_modified=False); self.db_set("output_batch",cb.name,update_modified=False)

    def on_submit(self):
        self.db_set("status","Completed"); self.db_set("completed_by",frappe.session.user)

    def on_cancel(self):
        if self.stock_entry:
            se=frappe.get_doc("Stock Entry",self.stock_entry)
            if se.docstatus==1: se.cancel()
        if self.coffee_batch:
            b=frappe.get_doc("Coffee Batch",self.coffee_batch); b.add_qty(self.input_qty, b.valuation_rate); b.save(ignore_permissions=True)
        if self.output_batch and frappe.db.exists("Coffee Batch",self.output_batch):
            b=frappe.get_doc("Coffee Batch",self.output_batch); b.qty=0; b.total_value=0; b.status="Rejected"; b.save(ignore_permissions=True)
        self.db_set("status","Cancelled")
