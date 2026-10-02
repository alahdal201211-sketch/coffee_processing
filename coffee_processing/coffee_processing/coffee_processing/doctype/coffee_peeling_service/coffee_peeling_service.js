frappe.ui.form.on('Coffee Peeling Service', {
    refresh(frm) {
        if (frm.doc.service_type === 'Customer Service' && frm.doc.docstatus === 1 && !frm.doc.sales_invoice) {
            frm.add_custom_button(__('إنشاء فاتورة الخدمة'), () => {
                frappe.call({
                    method: 'make_sales_invoice',
                    doc: frm.doc,
                    callback(r) {
                        if (r.message) {
                            frappe.msgprint(__('تم إنشاء فاتورة الخدمة: {0}', [r.message]));
                            frm.reload_doc();
                        }
                    }
                });
            }, __('الفوترة'));
        }
        if (frm.doc.sales_invoice) {
            frm.add_custom_button(__('فتح الفاتورة'), () => frappe.set_route('Form', 'Sales Invoice', frm.doc.sales_invoice), __('الفوترة'));
        }
    },
    service_type(frm) {
        frm.toggle_display('customer', frm.doc.service_type === 'Customer Service');
        frm.toggle_display('service_item', frm.doc.service_type === 'Customer Service');
    }
});
