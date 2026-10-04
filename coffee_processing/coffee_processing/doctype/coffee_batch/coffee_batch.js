frappe.ui.form.on('Coffee Batch', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('معلومات المخزون'), function() {
                frappe.call({
                    method: 'coffee_processing.coffee_processing.api.coffee_api.get_batch_info',
                    args: { batch_name: frm.doc.name },
                    callback: function(r) {
                        if (r.message) {
                            let msg = `
                                <table class="table table-bordered">
                                    <tr><td>${__('كود الصنف')}</td><td>${r.message.custom_item_code}</td></tr>
                                    <tr><td>${__('الكمية الحالية')}</td><td>${r.message.qty} KG</td></tr>
                                    <tr><td>${__('التكلفة لكل كجم')}</td><td>${r.message.cost_per_kg}</td></tr>
                                    <tr><td>${__('القيمة الإجمالية')}</td><td>${r.message.total_value}</td></tr>
                                    <tr><td>${__('الكمية المحجوزة')}</td><td>${r.message.reserved_qty} KG</td></tr>
                                    <tr><td>${__('الكمية المتاحة')}</td><td>${r.message.available_qty} KG</td></tr>
                                </table>`;
                            frappe.msgprint(msg);
                        }
                    }
                });
            }, __('عرض'));

            frm.add_custom_button(__('سلالة الدفعة'), function() {
                frappe.call({
                    method: 'coffee_processing.coffee_processing.api.coffee_api.get_batch_lineage_api',
                    args: { batch_name: frm.doc.name },
                    callback: function(r) {
                        if (r.message) {
                            let html = '<h4>' + __('سلالة الدفعة') + '</h4>';
                            if (r.message.ancestors.length) {
                                html += '<h5>' + __('الدفعات الأم') + '</h5><table class="table table-bordered">';
                                r.message.ancestors.forEach(function(a) {
                                    html += `<tr><td>${a.batch.name}</td><td>${a.batch.custom_item_code}</td><td>${a.batch.coffee_grade || '-'}</td></tr>`;
                                });
                                html += '</table>';
                            }
                            html += '<h5>' + __('الدفعة الحالية') + '</h5>';
                            html += `<table class="table table-bordered"><tr><td>${r.message.batch.name}</td><td>${r.message.batch.custom_item_code}</td><td>${r.message.batch.coffee_grade || '-'}</td></tr></table>`;
                            if (r.message.descendants.length) {
                                html += '<h5>' + __('الدفعات الفرعية') + '</h5><table class="table table-bordered">';
                                r.message.descendants.forEach(function(d) {
                                    html += `<tr><td>${d.batch.name}</td><td>${d.batch.custom_item_code}</td><td>${d.batch.coffee_grade || '-'}</td></tr>`;
                                });
                                html += '</table>';
                            }
                            frappe.msgprint(html);
                        }
                    }
                });
            }, __('عرض'));

            if (['Received', 'Ready for Processing'].includes(frm.doc.status)) {
                frm.add_custom_button(__('تقسيم الدفعة'), function() {
                    frappe.prompt([
                        {fieldname: 'split_qty', fieldtype: 'Float', label: __('الكمية'), reqd: 1},
                        {fieldname: 'new_warehouse', fieldtype: 'Link', label: __('المخزن الجديد'), options: 'Warehouse'}
                    ], function(values) {
                        frappe.call({
                            method: 'coffee_processing.coffee_processing.api.coffee_api.split_batch_api',
                            args: {
                                batch_name: frm.doc.name,
                                split_qty: values.split_qty,
                                new_warehouse: values.new_warehouse
                            },
                            callback: function(r) {
                                if (r.message) {
                                    frappe.msgprint(__('تم التقسيم') + ': ' + r.message.name);
                                    frm.reload_doc();
                                }
                            }
                        });
                    }, __('تقسيم'), __('تقسيم'));
                }, __('إجراءات'));
            }
        }
    },
    coffee_type: function(frm) {
        if (!['Specialty', 'Commercial'].includes(frm.doc.coffee_type)) {
            frm.set_value('coffee_grade', null);
        }
    },
    coffee_grade: function(frm) {
        if (frm.doc.coffee_grade && frm.doc.coffee_type) {
            frappe.db.get_doc('Coffee Grade Master', frm.doc.coffee_grade).then(grade => {
                if (frm.doc.coffee_type === 'Specialty' && grade.specialty_item_code) {
                    frm.set_value('custom_item_code', grade.specialty_item_code);
                } else if (frm.doc.coffee_type === 'Commercial' && grade.commercial_item_code) {
                    frm.set_value('custom_item_code', grade.commercial_item_code);
                }
            });
        }
    },
    company: function(frm) {
        frm.set_query('cost_center', function() {
            return { filters: { company: frm.doc.company } };
        });
        frm.set_query('route', function() {
            return { filters: { company: frm.doc.company } };
        });
    }
});
