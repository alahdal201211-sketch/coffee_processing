frappe.ui.form.on('Coffee Cost Center Mapping', {
    company: function(frm) {
        frm.set_query('cost_center', function() {
            return { filters: { company: frm.doc.company } };
        });
    }
});
