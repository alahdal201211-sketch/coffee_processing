frappe.ui.form.on("Supplier Region", {
    refresh(frm) {
        if (frm.doc.country) {
            frm.set_df_property("country", "read_only", 0);
        }
    }
});
