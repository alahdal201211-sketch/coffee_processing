import frappe
from frappe import _
from frappe.model.document import Document


class CoffeeReceivingSettings(Document):

    def validate(self):
        self._validate_company()
        self._validate_warehouses()
        self._validate_duplicates()

    def _validate_company(self):
        if not self.company:
            frappe.throw(_("الشركة مطلوبة."))

    def _validate_warehouses(self):
        if not self.source_warehouse:
            frappe.throw(_("مخزن المصدر مطلوب."))

        if not self.target_warehouse:
            frappe.throw(_("مخزن الهدف مطلوب."))

        if self.source_warehouse == self.target_warehouse:
            frappe.throw(
                _("يجب أن يكون مخزن المصدر مختلفًا عن مخزن الهدف.")
            )

        for fieldname, label in (
            ("source_warehouse", _("مخزن المصدر")),
            ("target_warehouse", _("مخزن الهدف")),
        ):
            warehouse = frappe.db.get_value(
                "Warehouse",
                self.get(fieldname),
                ["company", "disabled", "is_group"],
                as_dict=True,
            )

            if not warehouse:
                frappe.throw(
                    _("{0} غير موجود.").format(label)
                )

            if warehouse.company != self.company:
                frappe.throw(
                    _("{0} يجب أن يكون تابعًا للشركة المحددة.").format(label)
                )

            if warehouse.disabled:
                frappe.throw(
                    _("{0} معطل.").format(label)
                )

            if warehouse.is_group:
                frappe.throw(
                    _("{0} يجب أن يكون مخزنًا فعليًا وليس مجموعة مخازن.").format(label)
                )

    def _validate_duplicates(self):
        filters = {
            "company": self.company,
            "active": 1,
            "name": ["!=", self.name],
        }

        if self.branch:
            filters["branch"] = self.branch
        else:
            filters["branch"] = ["is", "not set"]

        if frappe.db.exists(
            "Coffee Receiving Settings",
            filters,
        ):
            frappe.throw(
                _(
                    "توجد إعدادات استلام فعالة أخرى لنفس الشركة والفرع."
                )
            )
