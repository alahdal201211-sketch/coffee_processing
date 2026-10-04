frappe.ui.form.on('Coffee Sample', {
    coffee_batch: function(frm) {
        if (frm.doc.coffee_batch) {
            frappe.db.get_doc('Coffee Batch', frm.doc.coffee_batch).then(batch => {
                frm.set_value('coffee_type', batch.coffee_type);
                frm.set_value('coffee_grade', batch.coffee_grade);
                frm.set_value('warehouse', batch.current_warehouse);
                frm.set_value('company', batch.company);
                frm.set_value('branch', batch.branch);
            });
        }
    }
});
