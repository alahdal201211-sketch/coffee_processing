frappe.ui.form.on('Coffee Process Order', {
    refresh(frm) {
        setup_coffee_process_order_ui(frm);
    },

    onload(frm) {
        setup_coffee_process_order_ui(frm);
    },

    operation(frm) {
        setup_coffee_process_order_ui(frm);
    },

    route(frm) {
        setup_coffee_process_order_ui(frm);
    },

    source_warehouse(frm) {
        setup_coffee_process_order_ui(frm);
    },

    target_warehouse(frm) {
        setup_coffee_process_order_ui(frm);
    },

    status(frm) {
        setup_coffee_process_order_ui(frm);
    },

    variance_status(frm) {
        setup_coffee_process_order_ui(frm);
    }
});


function setup_coffee_process_order_ui(frm) {
    if (!frm || !frm.page) {
        return;
    }

    frm.page.set_title(__('أمر معالجة البن'));

    hide_technical_fields(frm);
    render_current_operation_indicator(frm);
    render_process_summary(frm);
    render_variance_indicator(frm);
    render_cost_summary(frm);
}


function hide_technical_fields(frm) {
    const technical_fields = [
        'route_step_sequence',
        'operation_code',
        'operation_name_ar',
        'cost_allocation_method',
        'stock_entry_status',
        'stock_entry',
        'amended_from',
        'wip_account',
        'overhead_account',
        'variance_treatment_method',
        'variance_additional_qty',
        'variance_additional_cost',
        'variance_treatment_status'
    ];

    technical_fields.forEach(fieldname => {
        if (frm.fields_dict[fieldname]) {
            frm.set_df_property(fieldname, 'hidden', 1);
        }
    });
}


function render_current_operation_indicator(frm) {
    const operation =
        frm.doc.operation_name_ar ||
        frm.doc.operation ||
        __('غير محددة');

    const sequence = frm.doc.route_step_sequence || '';

    const html = `
        <div class="coffee-process-operation"
             style="
                margin: 12px 0;
                padding: 14px 18px;
                border: 1px solid var(--border-color);
                border-radius: 8px;
                background: var(--card-bg);
             ">

            <div style="
                font-size: 12px;
                color: var(--text-muted);
            ">
                ${__('العملية الحالية')}
            </div>

            <div style="
                font-size: 18px;
                font-weight: 600;
                margin-top: 4px;
            ">
                ${frappe.utils.escape_html(operation)}
            </div>

            ${
                sequence
                    ? `<div style="
                            margin-top: 6px;
                            font-size: 12px;
                            color: var(--text-muted);
                       ">
                            ${__('المرحلة')}: ${frappe.utils.escape_html(String(sequence))}
                       </div>`
                    : ''
            }

        </div>
    `;

    const field = frm.fields_dict.operation;

    if (field && field.$wrapper) {
        field.$wrapper.find('.coffee-process-operation').remove();
        field.$wrapper.after(html);
    }
}


function render_process_summary(frm) {
    const wrapper = frm.fields_dict.section_basic?.$wrapper;

    if (!wrapper) {
        return;
    }

    wrapper.find('.coffee-process-summary').remove();

    const status = frm.doc.status || __('غير محددة');
    const route = frm.doc.route || __('غير محدد');
    const branch = frm.doc.branch || __('غير محدد');

    const html = `
        <div class="coffee-process-summary"
             style="
                margin: 0 0 15px 0;
                padding: 12px 16px;
                border: 1px solid var(--border-color);
                border-radius: 8px;
                background: var(--fg-color);
             ">

            <div style="
                font-size: 13px;
                font-weight: 600;
                margin-bottom: 8px;
            ">
                ${__('ملخص أمر المعالجة')}
            </div>

            <div style="
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 10px;
            ">

                <div>
                    <div style="font-size:11px;color:var(--text-muted);">
                        ${__('المسار')}
                    </div>
                    <div style="font-weight:500;">
                        ${frappe.utils.escape_html(String(route))}
                    </div>
                </div>

                <div>
                    <div style="font-size:11px;color:var(--text-muted);">
                        ${__('الفرع')}
                    </div>
                    <div style="font-weight:500;">
                        ${frappe.utils.escape_html(String(branch))}
                    </div>
                </div>

                <div>
                    <div style="font-size:11px;color:var(--text-muted);">
                        ${__('الحالة')}
                    </div>
                    <div style="font-weight:500;">
                        ${frappe.utils.escape_html(String(status))}
                    </div>
                </div>

            </div>
        </div>
    `;

    wrapper.after(html);
}


function render_variance_indicator(frm) {
    const field = frm.fields_dict.variance_status;

    if (!field || !field.$wrapper) {
        return;
    }

    field.$wrapper.find('.coffee-process-variance-indicator').remove();

    const status = frm.doc.variance_status;

    if (!status || status === 'Within Threshold') {
        return;
    }

    let message = status;

    if (status === 'Requires Approval') {
        message = __('فرق الكمية يحتاج إلى موافقة');
    } else if (status === 'Approved') {
        message = __('تم اعتماد فرق الكمية');
    } else if (status === 'Rejected') {
        message = __('تم رفض فرق الكمية');
    }

    const html = `
        <div class="coffee-process-variance-indicator"
             style="
                margin-top: 8px;
                padding: 8px 12px;
                border-radius: 6px;
                border: 1px solid var(--border-color);
             ">
            ${frappe.utils.escape_html(message)}
        </div>
    `;

    field.$wrapper.append(html);
}


function render_cost_summary(frm) {
    const field = frm.fields_dict.output_cost_total;

    if (!field || !field.$wrapper) {
        return;
    }

    field.$wrapper.find('.coffee-process-cost-summary').remove();

    const inputCost = flt(frm.doc.input_cost_total);
    const processCost = flt(frm.doc.process_cost_total);
    const overheadCost = flt(frm.doc.overhead_cost_total);
    const byproductCredit = flt(frm.doc.byproduct_credit_total);
    const outputCost = flt(frm.doc.output_cost_total);

    const html = `
        <div class="coffee-process-cost-summary"
             style="
                margin-top: 10px;
                padding: 10px 12px;
                border: 1px solid var(--border-color);
                border-radius: 6px;
                font-size: 12px;
             ">

            <div style="font-weight:600;margin-bottom:6px;">
                ${__('ملخص التكلفة')}
            </div>

            <div>
                ${__('تكلفة المدخلات')}: ${format_currency(inputCost, frm.doc.currency)}
            </div>

            <div>
                ${__('تكلفة المعالجة')}: ${format_currency(processCost, frm.doc.currency)}
            </div>

            <div>
                ${__('التكاليف غير المباشرة')}: ${format_currency(overheadCost, frm.doc.currency)}
            </div>

            <div>
                ${__('ائتمان المنتجات الثانوية')}: ${format_currency(byproductCredit, frm.doc.currency)}
            </div>

            <div style="font-weight:600;margin-top:5px;">
                ${__('إجمالي تكلفة المخرجات')}: ${format_currency(outputCost, frm.doc.currency)}
            </div>

        </div>
    `;

    field.$wrapper.append(html);
}
