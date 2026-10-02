frappe.ui.form.on('Coffee Operation Master', {
    is_grading_operation: function(frm) {
        if (frm.doc.is_grading_operation) {
            frm.set_value('allow_multiple_outputs', 1);
            frm.set_value('cost_allocation_method', 'Hybrid');
        }
    }
});
