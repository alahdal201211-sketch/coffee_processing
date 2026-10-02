frappe.ui.form.on('Coffee Process Trial', {
    refresh(frm) {
        if (frm.doc.status === 'Approved' && !frm.doc.production_plan) {
            frm.add_custom_button(__('إنشاء خطة إنتاج'), () => {
                frappe.prompt(
                    [{fieldname:'planned_qty', fieldtype:'Float', label:__('الكمية المخططة (كجم)'), reqd:1}],
                    values => {
                        frappe.call({
                            method: 'coffee_processing.coffee_processing.api.coffee_api.create_production_plan_from_trial',
                            args: {trial_name: frm.doc.name, planned_qty: values.planned_qty},
                            freeze: true,
                            freeze_message: __('جاري إنشاء خطة الإنتاج...'),
                            callback(r) {
                                if (r.message) {
                                    frappe.show_alert({message: __('تم إنشاء خطة الإنتاج {0}', [r.message]), indicator: 'green'});
                                    frm.reload_doc();
                                }
                            }
                        });
                    },
                    __('إنشاء خطة إنتاج'),
                    __('إنشاء')
                );
            });
        }
    }
});
