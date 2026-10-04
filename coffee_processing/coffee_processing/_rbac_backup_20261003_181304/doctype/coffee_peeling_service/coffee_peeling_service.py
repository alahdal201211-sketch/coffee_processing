import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

class CoffeePeelingService(Document):
    def validate(self):
        if not self.inputs: frappe.throw(_("يجب إضافة دفعة واحدة على الأقل إلى خدمة التقشير."))
        if not self.outputs: frappe.throw(_("يجب تسجيل مخرجات التقشير الفعلية."))
        if flt(self.machine_capacity_tph)<=0: frappe.throw(_("طاقة آلة التقشير يجب أن تكون أكبر من صفر."))
        self.input_qty_total=sum(flt(r.qty) for r in self.inputs)
        self.output_qty_total=sum(flt(r.qty) for r in self.outputs if r.output_type != "Loss")
        self.loss_qty=max(self.input_qty_total-self.output_qty_total,0)
        self.yield_percent=(self.output_qty_total/self.input_qty_total*100) if self.input_qty_total else 0
        self.service_amount=self.input_qty_total*flt(self.service_rate_per_kg) if self.service_type=="Customer Service" else 0
        for r in self.outputs: r.percentage=(flt(r.qty)/self.input_qty_total*100) if self.input_qty_total else 0
        if self.service_type=="Customer Service" and not self.customer: frappe.throw(_("العميل مطلوب لخدمة التقشير."))

    def before_submit(self):
        if self.stock_entry: return
        from coffee_processing.coffee_processing.services.stock_service import create_repack_stock_entry
        inputs=[]
        total_input_cost=0
        for r in self.inputs:
            b=frappe.get_doc('Coffee Batch',r.coffee_batch)
            if not r.batch_no: r.batch_no=b.erpnext_batch
            rate=0 if self.service_type=='Customer Service' else flt(r.rate or b.cost_per_kg)
            r.rate=rate; r.amount=flt(r.qty)*rate; total_input_cost+=r.amount
            inputs.append({'item':r.item,'qty':r.qty,'uom':frappe.db.get_value('Item',r.item,'stock_uom'),'warehouse':r.warehouse,'batch_no':r.batch_no,'rate':rate})
        process_cost=flt(self.labor_cost)+flt(self.machine_cost)+flt(self.other_cost)
        total_cost=0 if self.service_type=='Customer Service' else total_input_cost+process_cost
        costable=[r for r in self.outputs if r.output_type!='Loss']
        qty_total=sum(flt(r.qty) for r in costable)
        for r in costable:
            r.valuation_rate=(total_cost*flt(r.qty)/qty_total/flt(r.qty)) if qty_total and self.service_type!='Customer Service' else 0
            r.amount=flt(r.qty)*flt(r.valuation_rate)
        stock_outputs=[]
        for r in self.outputs:
            if r.output_type=='Loss': continue
            stock_outputs.append({'item':r.item,'qty':r.qty,'uom':frappe.db.get_value('Item',r.item,'stock_uom'),'warehouse':r.warehouse,'rate':r.valuation_rate})
        se,rows=create_repack_stock_entry(self.company,self.service_date,inputs,stock_outputs,'Coffee Peeling Service '+self.name)
        self.stock_entry=se.name
        for r,(outrow,_se_row) in zip(costable,rows):
            out_batch=outrow.get('batch_no')
            source=frappe.get_doc('Coffee Batch',self.inputs[0].coffee_batch)
            new=frappe.new_doc('Coffee Batch')
            new.custom_item_code=r.item
            new.item_name=frappe.db.get_value('Item',r.item,'item_name') or r.item
            new.coffee_type=source.coffee_type
            new.coffee_grade=r.coffee_grade
            new.is_grade_batch=1 if r.coffee_grade else 0
            new.company=self.company; new.branch=self.branch
            new.source_type='Customer Service' if self.service_type=='Customer Service' else 'Processing'
            new.parent_batch=source.name; new.current_warehouse=r.warehouse
            new.qty=r.qty; new.valuation_rate=r.valuation_rate; new.cost_per_kg=r.valuation_rate; new.total_value=flt(r.qty)*flt(r.valuation_rate)
            new.status='Graded' if r.coffee_grade else 'In Process'
            new.cost_center=frappe.db.get_value('Coffee Operation Master','HULLING','default_cost_center')
            new.erpnext_batch=out_batch
            for inp in self.inputs:
                src=new.append('source_batches',{})
                src.source_batch=inp.coffee_batch; src.operation='HULLING'; src.qty_consumed=inp.qty; src.cost_amount=inp.amount
            new.insert(ignore_permissions=True)
            r.coffee_batch=new.name; r.batch_no=out_batch
        for r in self.inputs:
            b=frappe.get_doc('Coffee Batch',r.coffee_batch); b.reduce_qty(r.qty); b.save(ignore_permissions=True)

    def on_submit(self): self.db_set('status','Completed')
    def on_cancel(self):
        if self.stock_entry:
            se=frappe.get_doc('Stock Entry',self.stock_entry)
            if se.docstatus==1: se.cancel()
        self.db_set('status','Cancelled')
