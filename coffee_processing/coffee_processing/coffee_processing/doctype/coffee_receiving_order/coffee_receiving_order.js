frappe.ui.form.on("Coffee Receiving Order", {

    refresh(frm) {
        frm.set_intro(
            __("أمر استلام البن — إنشاء وربط دفعات الاستلام"),
            "blue"
        );

        if (!frm.is_new() && frm.doc.docstatus === 0) {
            frm.add_custom_button(
                __("إنشاء / ربط الدفعات"),
                function () {
                    frappe.call({
                        method: "create_batches",
                        doc: frm.doc,
                        freeze: true,
                        freeze_message: __("جاري إنشاء وربط الدفعات..."),
                        callback(r) {
                            if (!r.exc) {
                                frappe.show_alert({
                                    message: __("تم إنشاء وربط الدفعات بنجاح"),
                                    indicator: "green"
                                });

                                frm.reload_doc();
                            }
                        }
                    });
                },
                __("الدفعات")
            );
        }

        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(
                __("فتح الدفعات"),
                function () {
                    const batches = (frm.doc.inputs || [])
                        .map(row => row.coffee_batch)
                        .filter(Boolean);

                    if (!batches.length) {
                        frappe.msgprint(
                            __("لا توجد دفعات مرتبطة بهذا الأمر.")
                        );
                        return;
                    }

                    batches.forEach(batch => {
                        frappe.set_route(
                            "Form",
                            "Coffee Batch",
                            batch
                        );
                    });
                },
                __("الدفعات")
            );
        }

        update_receiving_totals(frm);
    },

    inputs_add(frm) {
        update_receiving_totals(frm);
    },

    inputs_remove(frm) {
        update_receiving_totals(frm);
    },

    initial_rate(frm) {
        update_receiving_totals(frm);
    },

    overhead_cost(frm) {
        update_receiving_totals(frm);
    },

    costs_add(frm) {
        update_receiving_totals(frm);
    },

    costs_remove(frm) {
        update_receiving_totals(frm);
    },

    costs_amount(frm) {
        update_receiving_totals(frm);
    },

    costs_qty(frm) {
        update_receiving_totals(frm);
    },

    costs_rate(frm) {
        update_receiving_totals(frm);
    }
});


function update_receiving_totals(frm) {

    let input_qty = 0;

    (frm.doc.inputs || []).forEach(row => {
        input_qty += flt(row.qty);
    });

    frm.set_value("input_qty_total", input_qty);
    frm.set_value("output_qty_total", input_qty);
    frm.set_value("loss_qty", 0);
    frm.set_value(
        "yield_percent",
        input_qty ? 100 : 0
    );

    let direct_cost = 0;

    (frm.doc.costs || []).forEach(row => {

        if (!flt(row.amount)) {
            row.amount = flt(row.qty) * flt(row.rate);
        }

        direct_cost += flt(row.amount);
    });

    frm.set_value("direct_cost", direct_cost);

    const total_cost =
        direct_cost +
        flt(frm.doc.overhead_cost) +
        (flt(frm.doc.initial_rate) * input_qty);

    frm.set_value("total_cost", total_cost);

    frm.set_value(
        "cost_per_kg",
        input_qty ? total_cost / input_qty : 0
    );
}
