import json
from pathlib import Path

import frappe
from frappe import _
from frappe.utils.nestedset import rebuild_tree


DATA_DIR = Path(__file__).resolve().parent / "data"


def load_data(filename):
    path = DATA_DIR / filename

    if not path.exists():
        frappe.throw(_("Coffee master data file not found: {0}").format(path))

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_existing(doctype, name):
    if frappe.db.exists(doctype, name):
        return frappe.get_doc(doctype, name)

    return None


def ensure_uoms():
    data = load_data("uoms.json")

    for row in data:
        name = row["uom_name"]

        doc = get_existing("UOM", name)

        if not doc:
            doc = frappe.get_doc({
                "doctype": "UOM",
                "uom_name": name,
                "must_be_whole_number": row.get("must_be_whole_number", 0),
            })

            doc.insert(ignore_permissions=True)
        else:
            changed = False

            if doc.must_be_whole_number != row.get("must_be_whole_number", 0):
                doc.must_be_whole_number = row.get("must_be_whole_number", 0)
                changed = True

            if changed:
                doc.save(ignore_permissions=True)


def ensure_company():
    rows = load_data("company.json")

    for row in rows:
        company_name = row["company_name"]
        company = frappe.db.exists("Company", company_name)

        if company:
            return frappe.get_doc("Company", company_name)

        # ERPNext automatically creates:
        # - Default Chart of Accounts
        # - Default Warehouses
        # - Default Cost Center
        #
        # We want coffee_processing to provide these explicitly
        # from its packaged master data instead.
        old_ignore_coa = getattr(frappe.local.flags, "ignore_chart_of_accounts", False)

        try:
            frappe.local.flags.ignore_chart_of_accounts = True

            company = frappe.get_doc({
                "doctype": "Company",
                "company_name": company_name,
                "abbr": row["abbr"],
                "default_currency": row["default_currency"],
                "country": row["country"],
            })

            # Prevent Company.on_update() from creating the default
            # Cost Center automatically.
            old_create_default_cost_center = getattr(
                company,
                "create_default_cost_center",
                None
            )

            company.create_default_cost_center = lambda: None

            company.insert(ignore_permissions=True)

            # Restore method reference is unnecessary after insert,
            # because this is a new document instance.

        finally:
            frappe.local.flags.ignore_chart_of_accounts = old_ignore_coa

        return company

    return None


def ensure_item_groups():
    data = load_data("item_groups.json")

    # Resolve the ERPNext root Item Group.
    # Fresh sites may use the English root or have no root yet.
    root_candidates = [
        "كل مجموعات الأصناف",
        "All Item Groups",
    ]

    root_name = next(
        (name for name in root_candidates if frappe.db.exists("Item Group", name)),
        None,
    )

    if not root_name:
        roots = frappe.get_all(
            "Item Group",
            filters={
                "parent_item_group": ["is", "not set"],
                "is_group": 1,
            },
            pluck="name",
        )

        if len(roots) == 1:
            root_name = roots[0]

    # On a completely fresh ERPNext site there may be no Item Group root.
    if not root_name:
        root_name = "All Item Groups"

        if not frappe.db.exists("Item Group", root_name):
            root = frappe.get_doc({
                "doctype": "Item Group",
                "item_group_name": root_name,
                "is_group": 1,
            })

            root.flags.ignore_mandatory = True
            root.insert(ignore_permissions=True)

    remaining = {
        row["item_group_name"]: row
        for row in data
    }

    safety = 0

    while remaining:
        safety += 1

        if safety > len(data) + 5:
            frappe.throw(
                _("Could not resolve Item Group hierarchy: {0}").format(
                    ", ".join(remaining.keys())
                )
            )

        progress = False

        for name, row in list(remaining.items()):
            parent = row.get("parent_item_group")

            # The coffee root originally belonged under the standard ERPNext root.
            if parent == "كل مجموعات الأصناف":
                parent = root_name

            # Parent belongs to the coffee package and must be created first.
            if parent and parent in remaining:
                continue

            doc = get_existing("Item Group", name)

            if not doc:
                doc = frappe.get_doc({
                    "doctype": "Item Group",
                    "item_group_name": name,
                    "parent_item_group": parent,
                    "is_group": row.get("is_group", 0),
                })

                doc.insert(ignore_permissions=True)

            else:
                changed = False

                if doc.parent_item_group != parent:
                    doc.parent_item_group = parent
                    changed = True

                if int(doc.is_group or 0) != int(row.get("is_group", 0)):
                    doc.is_group = row.get("is_group", 0)
                    changed = True

                if changed:
                    doc.save(ignore_permissions=True)

            del remaining[name]
            progress = True

        if not progress:
            frappe.throw(
                _("Could not resolve Item Group hierarchy: {0}").format(
                    ", ".join(remaining.keys())
                )
            )

    rebuild_tree("Item Group", "parent_item_group")

def ensure_accounts():
    """Create the packaged chart of accounts in dependency order.

    Account ``name`` is generated by ERPNext from account_name + company
    abbreviation.  Therefore parent references must be resolved to the
    *actual* database name after the parent is inserted, rather than assuming
    the packaged JSON name is always the final database name.
    """
    data = load_data("accounts.json")
    by_name = {row["name"]: row for row in data}
    remaining = dict(by_name)
    resolved_names = {}

    def resolve_existing(expected_name, row=None):
        """Return the actual Account name for a packaged account reference."""
        if expected_name in resolved_names:
            return resolved_names[expected_name]

        if frappe.db.exists("Account", expected_name):
            resolved_names[expected_name] = expected_name
            return expected_name

        source = row or by_name.get(expected_name)
        if source:
            actual = frappe.db.get_value(
                "Account",
                {
                    "account_name": source.get("account_name"),
                    "company": source.get("company"),
                },
                "name",
            )
            if actual:
                resolved_names[expected_name] = actual
                return actual

        return None

    safety = 0
    while remaining:
        safety += 1
        if safety > len(data) + 10:
            frappe.throw(
                _("Could not resolve Account hierarchy: {0}").format(
                    ", ".join(remaining.keys())
                )
            )

        progress = False

        for expected_name, row in list(remaining.items()):
            expected_parent = row.get("parent_account")
            actual_parent = None

            if expected_parent:
                actual_parent = resolve_existing(expected_parent)
                if not actual_parent:
                    # Parent is packaged but has not been created yet.
                    if expected_parent in remaining:
                        continue
                    frappe.throw(
                        _(
                            "Parent Account {0} is not available for {1}."
                        ).format(expected_parent, expected_name)
                    )

            values = {
                "doctype": "Account",
                "account_name": row.get("account_name") or expected_name,
                "account_number": row.get("account_number"),
                "is_group": row.get("is_group", 0),
                "company": row.get("company"),
                "root_type": row.get("root_type"),
                "report_type": row.get("report_type"),
                "account_currency": row.get("account_currency"),
                "parent_account": actual_parent,
                "account_type": row.get("account_type"),
                "tax_rate": row.get("tax_rate"),
                "freeze_account": row.get("freeze_account"),
                "balance_must_be": row.get("balance_must_be"),
                "disabled": row.get("disabled", 0),
            }
            values = {k: v for k, v in values.items() if v is not None}

            doc = resolve_existing(expected_name, row)
            if doc:
                doc = frappe.get_doc("Account", doc)
                changed = False
                for field in (
                    "account_name", "account_number", "is_group", "company",
                    "root_type", "report_type", "account_currency",
                    "parent_account", "account_type", "tax_rate",
                    "freeze_account", "balance_must_be", "disabled",
                ):
                    if field not in values:
                        continue
                    if getattr(doc, field, None) != values[field]:
                        setattr(doc, field, values[field])
                        changed = True
                # ERPNext does not allow editing Root Accounts.
                # Keep existing roots untouched; synchronize only non-root accounts.
                is_existing_root = (
                    not doc.parent_account
                    and doc.is_group == 1
                    and doc.root_type in {
                        "Asset", "Liability", "Equity", "Income", "Expense"
                    }
                )

                if changed and not is_existing_root:
                    doc.save(ignore_permissions=True)

                actual_name = doc.name
            else:
                doc = frappe.get_doc(values)
                if (
                    not actual_parent
                    and values.get("is_group") == 1
                    and values.get("root_type") in {
                        "Asset", "Liability", "Equity", "Income", "Expense"
                    }
                ):
                    doc.flags.ignore_mandatory = True
                doc.insert(ignore_permissions=True)
                actual_name = doc.name

            # Verify immediately: later children must reference a real parent.
            if not frappe.db.exists("Account", actual_name):
                frappe.throw(
                    _("Account {0} was not created correctly.").format(expected_name)
                )

            resolved_names[expected_name] = actual_name
            del remaining[expected_name]
            progress = True

        if not progress:
            unresolved = ", ".join(remaining.keys())
            frappe.throw(_("Could not resolve Account hierarchy: {0}").format(unresolved))

    rebuild_tree("Account")

def ensure_warehouses():
    data = load_data("warehouses.json")

    remaining = {
        row["name"]: row
        for row in data
    }

    safety = 0

    while remaining:
        safety += 1

        if safety > len(data) + 10:
            frappe.throw(
                _("Could not resolve Warehouse hierarchy: {0}").format(
                    ", ".join(remaining.keys())
                )
            )

        progress = False

        for name, row in list(remaining.items()):
            parent = row.get("parent_warehouse")
            actual_parent = None

            if parent:
                # First use the packaged name when it already exists.
                actual_parent = get_existing("Warehouse", parent)

                # ERPNext generates Warehouse names using the company
                # abbreviation. Resolve the logical parent name when the
                # packaged name differs from the actual database name.
                if not actual_parent:
                    parent_row = next(
                        (
                            r for r in data
                            if r.get("name") == parent
                        ),
                        None,
                    )

                    if parent_row:
                        existing_parent_name = frappe.db.get_value(
                            "Warehouse",
                            {
                                "warehouse_name": parent_row.get("warehouse_name"),
                                "company": parent_row.get("company"),
                            },
                            "name",
                        )

                        if existing_parent_name:
                            actual_parent = frappe.get_doc(
                                "Warehouse",
                                existing_parent_name,
                            )

                # Parent is packaged but has not been created yet.
                if not actual_parent and parent in remaining:
                    continue

                if not actual_parent:
                    frappe.throw(
                        _("Parent Warehouse {0} is not available for {1}.").format(
                            parent, name
                        )
                    )

                actual_parent = actual_parent.name

            # Resolve the packaged stock account to the actual ERPNext
            # Account name generated for this company.
            #
            # Example:
            #   packaged: "البن الخام - ALC"
            #   actual:   "البن الخام - بن1"
            #
            # Never create duplicate "- ALC" accounts. The logical
            # account_name + company identifies the real Account.

            account = row.get("account")

            if account:
                actual_account = frappe.db.get_value(
                    "Account",
                    account,
                    "name",
                )

                if not actual_account:
                    accounts_data = load_data("accounts.json")

                    account_row = next(
                        (
                            r for r in accounts_data
                            if r.get("name") == account
                        ),
                        None,
                    )

                    if account_row:
                        actual_account = frappe.db.get_value(
                            "Account",
                            {
                                "account_name": account_row.get("account_name"),
                                "company": row.get("company"),
                            },
                            "name",
                        )

                if not actual_account:
                    frappe.throw(
                        _(
                            "Could not resolve Account {0} for Warehouse {1}."
                        ).format(account, name)
                    )

                account = actual_account

            values = {
                "doctype": "Warehouse",
                "warehouse_name": row.get("warehouse_name") or name,
                "is_group": row.get("is_group", 0),
                "parent_warehouse": actual_parent,
                "is_rejected_warehouse": row.get(
                    "is_rejected_warehouse", 0
                ),
                "account": account,
                "company": row.get("company"),
            }

            values = {
                k: v for k, v in values.items()
                if v is not None
            }

            doc = get_existing("Warehouse", name)

            # ERPNext generates Warehouse names as:
            # warehouse_name + " - " + company abbreviation.
            # Resolve an existing warehouse by its logical name and company
            # when the packaged name is not the generated database name.
            if not doc:
                existing_name = frappe.db.get_value(
                    "Warehouse",
                    {
                        "warehouse_name": values.get("warehouse_name"),
                        "company": values.get("company"),
                    },
                    "name",
                )

                if existing_name:
                    doc = frappe.get_doc("Warehouse", existing_name)

            if not doc:
                doc = frappe.get_doc(values)

                # ERPNext root accounts legitimately have no parent_account.
                # The five ALC root accounts are:
                # Asset, Liability, Equity, Income, Expense.
                is_root_account = (
                    not parent
                    and values.get("is_group") == 1
                    and values.get("root_type")
                    in {"Asset", "Liability", "Equity", "Income", "Expense"}
                )

                if is_root_account:
                    doc.flags.ignore_mandatory = True

                doc.insert(ignore_permissions=True)
            else:
                changed = False

                fields = [
                    "warehouse_name",
                    "is_group",
                    "parent_warehouse",
                    "is_rejected_warehouse",
                    "account",
                    "company",
                ]

                for field in fields:
                    if field not in values:
                        continue

                    new_value = values[field]

                    if getattr(doc, field, None) != new_value:
                        setattr(doc, field, new_value)
                        changed = True

                if changed:
                    doc.save(ignore_permissions=True)

            del remaining[name]
            progress = True

        if not progress:
            frappe.throw(
                _("Could not resolve Warehouse hierarchy: {0}").format(
                    ", ".join(remaining.keys())
                )
            )

    rebuild_tree("Warehouse", "parent_warehouse")


def ensure_cost_centers():
    data = load_data("cost_centers.json")

    remaining = {
        row["name"]: row
        for row in data
    }

    safety = 0

    while remaining:
        safety += 1

        if safety > len(data) + 5:
            frappe.throw(
                _("Could not resolve Cost Center hierarchy: {0}").format(
                    ", ".join(remaining.keys())
                )
            )

        progress = False

        for name, row in list(remaining.items()):
            parent = row.get("parent_cost_center")
            actual_parent = None

            # Resolve the packaged parent Cost Center name to the actual
            # ERPNext Cost Center name for this company.
            #
            # Example:
            #   packaged: "الاهدل للبن - ALC"
            #   actual:   "الاهدل للبن - بن1"

            if parent:
                actual_parent = get_existing("Cost Center", parent)

                if actual_parent:
                    actual_parent = actual_parent.name
                else:
                    parent_row = next(
                        (
                            r
                            for r in data
                            if r.get("name") == parent
                        ),
                        None,
                    )

                    if parent_row:
                        existing_parent_name = frappe.db.get_value(
                            "Cost Center",
                            {
                                "cost_center_name": parent_row.get(
                                    "cost_center_name"
                                ),
                                "company": row["company"],
                            },
                            "name",
                        )

                        if existing_parent_name:
                            actual_parent = existing_parent_name

                if not actual_parent:
                    if parent in remaining:
                        continue

                    frappe.throw(
                        _(
                            "Could not resolve parent Cost Center {0} "
                            "for {1}."
                        ).format(parent, name)
                    )

            values = {
                "doctype": "Cost Center",
                "cost_center_name": row["cost_center_name"],
                "company": row["company"],
                "is_group": row.get("is_group", 0),
                "disabled": row.get("disabled", 0),
            }

            if actual_parent:
                values["parent_cost_center"] = actual_parent

            # Resolve the packaged Cost Center name to the actual
            # ERPNext name generated for this company.
            #
            # Example:
            #   packaged: "الاهدل للبن - ALC"
            #   actual:   "الاهدل للبن - بن1"
            #
            # Match by logical cost_center_name + company so we never
            # create a duplicate root/child Cost Center.

            doc = get_existing("Cost Center", name)

            if not doc:
                existing_name = frappe.db.get_value(
                    "Cost Center",
                    {
                        "cost_center_name": row["cost_center_name"],
                        "company": row["company"],
                    },
                    "name",
                )

                if existing_name:
                    doc = frappe.get_doc("Cost Center", existing_name)

            if not doc:
                doc = frappe.get_doc(values)

                # The root Cost Center legitimately has no parent.
                if not parent and int(row.get("is_group", 0)) == 1:
                    doc.flags.ignore_mandatory = True

                doc.insert(ignore_permissions=True)

            else:
                changed = False

                if doc.cost_center_name != row["cost_center_name"]:
                    doc.cost_center_name = row["cost_center_name"]
                    changed = True

                if doc.company != row["company"]:
                    doc.company = row["company"]
                    changed = True

                if doc.parent_cost_center != actual_parent:
                    doc.parent_cost_center = actual_parent
                    changed = True

                if int(doc.is_group or 0) != int(row.get("is_group", 0)):
                    doc.is_group = row.get("is_group", 0)
                    changed = True

                if int(doc.disabled or 0) != int(row.get("disabled", 0)):
                    doc.disabled = row.get("disabled", 0)
                    changed = True

                if changed:
                    doc.save(ignore_permissions=True)

            del remaining[name]
            progress = True

        if not progress:
            frappe.throw(
                _("Could not resolve Cost Center hierarchy: {0}").format(
                    ", ".join(remaining.keys())
                )
            )

    rebuild_tree("Cost Center", "parent_cost_center")

def ensure_items():
    data = load_data("items.json")

    for row in data:
        item_code = row["item_code"]

        values = {
            "doctype": "Item",
            "item_code": item_code,
            "item_name": row.get("item_name") or item_code,
            "item_group": row["item_group"],
            "stock_uom": row["stock_uom"],
            "disabled": row.get("disabled", 0),
            "is_stock_item": row.get("is_stock_item", 1),
            "is_fixed_asset": row.get("is_fixed_asset", 0),
            "has_variants": row.get("has_variants", 0),
            "valuation_method": row.get(
                "valuation_method",
                "Moving Average"
            ),
            "allow_negative_stock": row.get(
                "allow_negative_stock",
                0
            ),
            "has_batch_no": row.get("has_batch_no", 0),
            "create_new_batch": row.get("create_new_batch", 0),
            "batch_number_series": row.get(
                "batch_number_series",
                "COF-BATCH-.YYYY.-.#####"
                if (
                    row.get("has_batch_no", 0) == 1
                    and row.get("is_stock_item", 1) == 1
                    and row.get("is_purchase_item", 1) == 1
                )
                else None
            ),
            "has_serial_no": row.get("has_serial_no", 0),
            "is_purchase_item": row.get("is_purchase_item", 1),
            "is_sales_item": row.get("is_sales_item", 1),
            "include_item_in_manufacturing": row.get(
                "include_item_in_manufacturing",
                1
            ),
            "default_material_request_type": row.get(
                "default_material_request_type",
                "Purchase"
            ),
            "end_of_life": row.get(
                "end_of_life",
                "2099-12-31"
            ),
        }

        doc = get_existing("Item", item_code)

        if not doc:
            doc = frappe.get_doc(values)
            doc.insert(ignore_permissions=True)
        else:
            changed = False

            fields = [
                "item_name",
                "item_group",
                "stock_uom",
                "disabled",
                "is_stock_item",
                "is_fixed_asset",
                "has_variants",
                "valuation_method",
                "allow_negative_stock",
                "has_batch_no",
                "create_new_batch",
                "batch_number_series",
                "has_serial_no",
                "is_purchase_item",
                "is_sales_item",
                "include_item_in_manufacturing",
                "default_material_request_type",
                "end_of_life",
            ]

            for field in fields:
                if field not in values:
                    continue

                new_value = values[field]

                if getattr(doc, field, None) != new_value:
                    setattr(doc, field, new_value)
                    changed = True

            if changed:
                doc.save(ignore_permissions=True)


def update_company_defaults():
    """Update Company defaults using actual ERPNext link names.

    Packaged master data may use the historical ``- ALC`` suffix while
    ERPNext generates the real Account / Cost Center / Warehouse names
    from the company's abbreviation. Resolve those links before saving.
    """
    data = load_data("company.json")

    if not data:
        return

    row = data[0]
    company_name = row["company_name"]

    company = frappe.get_doc("Company", company_name)

    account_fields = {
        "default_bank_account",
        "default_cash_account",
        "default_receivable_account",
        "default_payable_account",
        "write_off_account",
        "unrealized_profit_loss_account",
        "default_expense_account",
        "default_income_account",
        "default_discount_account",
        "exchange_gain_loss_account",
        "unrealized_exchange_loss_account",
        "round_off_account",
        "deferred_revenue_account",
        "deferred_expense_account",
        "accumulated_depreciation_account",
        "depreciation_expense_account",
        "expenses_included_in_asset_valuation",
        "disposal_account",
        "capital_work_in_progress_account",
        "asset_received_but_not_billed",
        "default_inventory_account",
        "stock_adjustment_account",
        "stock_received_but_not_billed",
        "expenses_included_in_valuation",
        "default_operating_cost_account",
    }

    cost_center_fields = {
        "cost_center",
        "round_off_cost_center",
        "depreciation_cost_center",
    }

    def resolve_account(value):
        """Resolve packaged Account name to the actual Account name."""
        if not value:
            return value

        if frappe.db.exists("Account", value):
            return value

        logical_name = value

        if logical_name.endswith(" - ALC"):
            logical_name = logical_name[:-6]

        actual = frappe.db.get_value(
            "Account",
            {
                "account_name": logical_name,
                "company": company_name,
            },
            "name",
        )

        if actual:
            return actual

        return value

    def resolve_cost_center(value):
        """Resolve packaged Cost Center name to the actual name."""
        if not value:
            return value

        if frappe.db.exists("Cost Center", value):
            return value

        logical_name = value

        if logical_name.endswith(" - ALC"):
            logical_name = logical_name[:-6]

        actual = frappe.db.get_value(
            "Cost Center",
            {
                "cost_center_name": logical_name,
                "company": company_name,
            },
            "name",
        )

        if actual:
            return actual

        return value

    def resolve_warehouse(value):
        """Resolve packaged Warehouse name to the actual warehouse name."""
        if not value:
            return value

        if frappe.db.exists("Warehouse", value):
            return value

        logical_name = value

        if logical_name.endswith(" - ALC"):
            logical_name = logical_name[:-6]

        actual = frappe.db.get_value(
            "Warehouse",
            {
                "warehouse_name": logical_name,
                "company": company_name,
            },
            "name",
        )

        if actual:
            return actual

        return value

    fields = [
        "default_bank_account",
        "default_cash_account",
        "default_receivable_account",
        "default_payable_account",
        "write_off_account",
        "unrealized_profit_loss_account",
        "default_expense_account",
        "default_income_account",
        "default_discount_account",
        "cost_center",
        "exchange_gain_loss_account",
        "unrealized_exchange_loss_account",
        "round_off_account",
        "round_off_cost_center",
        "deferred_revenue_account",
        "deferred_expense_account",
        "accumulated_depreciation_account",
        "depreciation_expense_account",
        "expenses_included_in_asset_valuation",
        "disposal_account",
        "depreciation_cost_center",
        "capital_work_in_progress_account",
        "asset_received_but_not_billed",
        "enable_perpetual_inventory",
        "default_inventory_account",
        "stock_adjustment_account",
        "default_in_transit_warehouse",
        "stock_received_but_not_billed",
        "expenses_included_in_valuation",
        "default_operating_cost_account",
    ]

    changed = False

    for field in fields:
        if field not in row:
            continue

        value = row.get(field)

        if value is None or value == "":
            continue

        if field in account_fields:
            value = resolve_account(value)

        elif field in cost_center_fields:
            value = resolve_cost_center(value)

        elif field == "default_in_transit_warehouse":
            value = resolve_warehouse(value)

        if getattr(company, field, None) != value:
            setattr(company, field, value)
            changed = True

    if changed:
        company.save(ignore_permissions=True)

def ensure_currencies():
    """Ensure the three business currencies exist; YER remains the company currency.

    Exchange rates are deliberately NOT hard-coded. ERPNext Exchange Rate / Payment Entry
    should provide the actual rate at the time of payment.
    """
    for code in ("YER", "SAR", "USD"):
        if not frappe.db.exists("Currency", code):
            doc = frappe.get_doc({"doctype": "Currency", "name": code})
            # Currency is a core DocType; setting only name lets ERPNext apply defaults.
            doc.insert(ignore_permissions=True)


def ensure_supplier_fields():
    """Add the supplier master fields required by the coffee procurement workflow."""
    fields = [
        {
            "fieldname": "coffee_region",
            "label": "منطقة البن",
            "fieldtype": "Link",
            "options": "Supplier Region",
            "insert_after": "region",
            "in_list_view": 0,
        },
        {
            "fieldname": "coffee_city",
            "label": "المدينة",
            "fieldtype": "Data",
            "insert_after": "coffee_region",
            "in_list_view": 1,
        },
        {
            "fieldname": "coffee_altitude_m",
            "label": "ارتفاع المنطقة (متر)",
            "fieldtype": "Float",
            "insert_after": "coffee_city",
        },
        {
            "fieldname": "coffee_type",
            "label": "نوع البن",
            "fieldtype": "Select",
            "options": "دوايري\nتفاحي\nأخرى",
            "insert_after": "coffee_altitude_m",
            "in_list_view": 1,
        },
    ]
    for spec in fields:
        if frappe.db.exists("Custom Field", {"dt": "Supplier", "fieldname": spec["fieldname"]}):
            continue
        doc = frappe.get_doc({"doctype": "Custom Field", "dt": "Supplier", **spec})
        doc.insert(ignore_permissions=True)


def ensure_supplier_regions():
    data = load_data("business_master.json").get("supplier_regions", [])
    for country, city, region in data:
        name = region
        if frappe.db.exists("Supplier Region", name):
            doc = frappe.get_doc("Supplier Region", name)
            if doc.country != country and frappe.db.exists("Country", country):
                doc.country = country
                doc.save(ignore_permissions=True)
            continue
        if not frappe.db.exists("Country", country):
            # Standard ERPNext sites normally have Yemen. If not, fail clearly.
            frappe.throw(_("Country {0} is required for Supplier Region {1}.").format(country, name))
        doc = frappe.get_doc({"doctype":"Supplier Region","region_name":name,"country":country,"city":city,"active":1})
        doc.insert(ignore_permissions=True)


def ensure_roles():
    roles = [
        "Coffee Processing Manager", "Coffee Receiving User", "Coffee Batch User",
        "Coffee Sorting User", "Coffee Fermentation User", "Coffee Drying User",
        "Coffee Hulling User", "Coffee Grading User", "Coffee Cupping User",
        "Coffee Packaging User", "Coffee Blending User", "Coffee Accountant",
    ]
    for role_name in roles:
        if not frappe.db.exists("Role", role_name):
            doc = frappe.get_doc({"doctype":"Role","role_name":role_name})
            doc.insert(ignore_permissions=True)


def ensure_bank_and_wallet_accounts():
    """Create generic YER/SAR/USD bank and wallet ledgers without inventing institutions.

    Resolve packaged ``- ALC`` account references to the actual ERPNext
    account names generated for the company abbreviation.
    """
    company = "الاهدل للبن"

    # Packaged parent definitions:
    #   (logical account name, packaged parent reference, root type)
    parents = [
        (
            "حسابات بنكية متعددة العملات",
            "حسابات مصرفية",
            "Asset",
        ),
        (
            "محافظ إلكترونية متعددة العملات",
            "أصول متداولة",
            "Asset",
        ),
    ]

    def resolve_account(logical_name):
        """Resolve an account by logical account_name + company."""
        packaged_name = f"{logical_name} - ALC"

        # First accept the packaged name if it already exists.
        existing = frappe.db.get_value(
            "Account",
            packaged_name,
            "name",
        )
        if existing:
            return existing

        # Normal ERPNext naming uses the company abbreviation.
        existing = frappe.db.get_value(
            "Account",
            {
                "account_name": logical_name,
                "company": company,
            },
            "name",
        )

        return existing

    resolved_parents = {}

    for logical_name, parent_logical_name, root_type in parents:
        actual_parent = resolve_account(logical_name)

        if not actual_parent:
            actual_parent = resolve_account(parent_logical_name)

        if not actual_parent:
            frappe.throw(
                _(
                    "Could not resolve parent Account {0} for company {1}."
                ).format(
                    logical_name,
                    company,
                )
            )

        resolved_parents[logical_name] = actual_parent

    rows = []

    for kind, parent_logical_name in [
        (
            "بنك",
            "حسابات بنكية متعددة العملات",
        ),
        (
            "محفظة إلكترونية",
            "محافظ إلكترونية متعددة العملات",
        ),
    ]:
        parent = resolved_parents[parent_logical_name]

        for cur in ("YER", "SAR", "USD"):
            logical_name = f"{kind} {cur}"

            rows.append(
                (
                    logical_name,
                    kind,
                    cur,
                    parent,
                )
            )

    for logical_name, kind, cur, parent in rows:
        actual_name = resolve_account(logical_name)

        if actual_name:
            continue

        values = {
            "doctype": "Account",
            "account_name": logical_name,
            "company": company,
            "root_type": "Asset",
            "report_type": "Balance Sheet",
            "is_group": 0,
            "account_currency": cur,
            "parent_account": parent,
            "account_type": "Bank" if kind == "بنك" else "Cash",
        }

        doc = frappe.get_doc(values)
        doc.insert(ignore_permissions=True)

def ensure_process_cost_links():
    """Link each configured coffee operation to its actual Cost Center.

    Packaged master data uses the historical ``- ALC`` suffix, while
    ERPNext generates the actual Cost Center name using the company's
    abbreviation (for example ``- بن1``). Resolve the logical
    Cost Center by ``cost_center_name`` + company instead of relying
    on the packaged document name.
    """
    company = "الاهدل للبن"

    mapping = {
        "RECEIVING": "استلام البن - البن - ALC",
        "SORTING": "الفرز - البن - ALC",
        "FERMENTATION": "التخمير - البن - ALC",
        "DRYING": "التجفيف - البن - ALC",
        "HULLING": "التقشير - البن - ALC",
        "GRADING": "التصنيف - البن - ALC",
        "CUPPING": "التذوق والتقييم - البن - ALC",
        "PACKAGING": "التعبئة - البن - ALC",
        "BLENDING": "الخلط - البن - ALC",
    }

    for operation_code, cost_center_name in mapping.items():
        if not frappe.db.exists(
            "Coffee Operation Master",
            operation_code,
        ):
            continue

        actual_cost_center = frappe.db.get_value(
            "Cost Center",
            {
                "cost_center_name": cost_center_name,
                "company": company,
            },
            "name",
        )

        if not actual_cost_center:
            frappe.throw(
                _(
                    "Could not resolve Cost Center {0} for operation {1}."
                ).format(
                    cost_center_name,
                    operation_code,
                )
            )

        doc = frappe.get_doc(
            "Coffee Operation Master",
            operation_code,
        )

        if doc.default_cost_center != actual_cost_center:
            doc.default_cost_center = actual_cost_center
            doc.save(ignore_permissions=True)






def remove_legacy_coffee_number_cards():
    """
    Remove the obsolete legacy Coffee Processing Number Cards.

    The current dashboard is driven exclusively by fixtures/number_card.json
    and contains 12 Arabic KPI cards. These legacy cards are no longer part
    of the application and must not survive migration.

    This operation is idempotent:
    - no action when legacy cards do not exist
    - refuses to delete a legacy card that is still linked to a dashboard
    - removes only the known obsolete Coffee Processing cards
    """

    legacy_cards = [
        "Coffee Total Batches",
        "Coffee Current Qty",
        "Coffee Inventory Value",
        "Coffee In Progress Orders",
        "Coffee Completed Orders",
        "Coffee Input Qty",
        "Coffee Output Qty",
        "Coffee Loss Qty",
        "Coffee Production Plans",
    ]

    for card_name in legacy_cards:

        if not frappe.db.exists("Number Card", card_name):
            continue

        linked = frappe.db.sql(
            """
            SELECT parent, idx
            FROM `tabNumber Card Link`
            WHERE card = %s
            ORDER BY parent, idx
            """,
            (card_name,),
            as_dict=True,
        )

        if linked:
            frappe.throw(
                _(
                    "Cannot remove legacy Number Card {0} because it is "
                    "still linked to Dashboard {1}."
                ).format(
                    card_name,
                    ", ".join(
                        f"{row.parent} (idx {row.idx})"
                        for row in linked
                    ),
                )
            )

        frappe.db.sql(
            """
            DELETE FROM `tabNumber Card`
            WHERE name = %s
            """,
            (card_name,),
        )

    # Final verification.
    remaining = frappe.db.sql(
        """
        SELECT name
        FROM `tabNumber Card`
        WHERE name IN (
            'Coffee Total Batches',
            'Coffee Current Qty',
            'Coffee Inventory Value',
            'Coffee In Progress Orders',
            'Coffee Completed Orders',
            'Coffee Input Qty',
            'Coffee Output Qty',
            'Coffee Loss Qty',
            'Coffee Production Plans'
        )
        ORDER BY name
        """,
        as_dict=True,
    )

    if remaining:
        frappe.throw(
            _(
                "Legacy Coffee Number Cards still exist after cleanup: {0}"
            ).format(
                ", ".join(row.name for row in remaining)
            )
        )


def ensure_coffee_dashboard():
    """
    Ensure the main Coffee Processing dashboard exists and is fully linked
    to the packaged Number Cards and Dashboard Charts.

    This function is idempotent:
    - creates the dashboard when missing
    - keeps it non-standard and in the Coffee Processing module
    - removes stale card/chart links
    - restores the exact packaged KPI cards
    - restores the exact packaged dashboard charts
    """

    dashboard_name = "Coffee Dashboard"

    # ------------------------------------------------------------------
    # 1. Create / normalize dashboard
    # ------------------------------------------------------------------
    if frappe.db.exists("Dashboard", dashboard_name):
        dashboard = frappe.get_doc("Dashboard", dashboard_name)
    else:
        dashboard = frappe.get_doc({
            "doctype": "Dashboard",
            "dashboard_name": dashboard_name,
            "module": "Coffee Processing",
            "is_standard": 0,
        })
        dashboard.insert(ignore_permissions=True)

    changed = False

    if dashboard.dashboard_name != dashboard_name:
        dashboard.dashboard_name = dashboard_name
        changed = True

    if dashboard.module != "Coffee Processing":
        dashboard.module = "Coffee Processing"
        changed = True

    if int(dashboard.is_standard or 0) != 0:
        dashboard.is_standard = 0
        changed = True

    # ------------------------------------------------------------------
    # 2. Exact KPI cards that belong to the Coffee Dashboard
    # ------------------------------------------------------------------
    card_names = [
        "إجمالي دفعات البن",
        "دفعات قيد المعالجة",
        "دفعات مكتملة",
        "دفعات جاهزة للمعالجة",
        "إجمالي كمية الدفعات",
        "إجمالي قيمة الدفعات",
        "إجمالي أوامر المعالجة",
        "أوامر قيد التنفيذ",
        "أوامر مكتملة",
        "أوامر بانتظار الموافقة",
        "أوامر فرق تحتاج موافقة",
        "إجمالي تكلفة المعالجة",
    ]

    # Make sure every packaged card exists.
    for card_name in card_names:
        if not frappe.db.exists("Number Card", card_name):
            frappe.throw(
                _(
                    "Required Number Card {0} does not exist. "
                    "Check fixtures/number_card.json before migrating."
                ).format(card_name)
            )

    # Rebuild the child table so stale/duplicate links disappear.
    dashboard.set("cards", [])

    for card_name in card_names:
        dashboard.append("cards", {
            "card": card_name,
        })

    # ------------------------------------------------------------------
    # 3. Exact charts that belong to the Coffee Dashboard
    # ------------------------------------------------------------------
    chart_names = [
        "حالة دفعات البن",
        "حالة أوامر المعالجة",
        "أنواع البن",
        "العمليات المنفذة",
        "الكمية الداخلة حسب العملية",
        "الكمية الخارجة حسب العملية",
        "الفاقد حسب العملية",
        "تكلفة المعالجة حسب العملية",
    ]

    # Make sure every packaged chart exists.
    for chart_name in chart_names:
        if not frappe.db.exists("Dashboard Chart", chart_name):
            frappe.throw(
                _(
                    "Required Dashboard Chart {0} does not exist."
                ).format(chart_name)
            )

    # Rebuild chart links to guarantee exact ordering and no duplicates.
    dashboard.set("charts", [])

    for idx, chart_name in enumerate(chart_names, start=1):
        dashboard.append("charts", {
            "chart": chart_name,
            "width": "Half",
        })

    # ------------------------------------------------------------------
    # 4. Save once after rebuilding both child tables
    # ------------------------------------------------------------------
    dashboard.save(ignore_permissions=True)

    # ------------------------------------------------------------------
    # 5. Verify the result immediately
    # ------------------------------------------------------------------
    dashboard.reload()

    actual_cards = [
        row.card
        for row in dashboard.cards
    ]

    actual_charts = [
        row.chart
        for row in dashboard.charts
    ]

    if actual_cards != card_names:
        frappe.throw(
            _(
                "Coffee Dashboard card links are incorrect. "
                "Expected {0}, got {1}."
            ).format(
                len(card_names),
                len(actual_cards),
            )
        )

    if actual_charts != chart_names:
        frappe.throw(
            _(
                "Coffee Dashboard chart links are incorrect. "
                "Expected {0}, got {1}."
            ).format(
                len(chart_names),
                len(actual_charts),
            )
        )
        
        
def ensure_coffee_resources():
    """Converge physical processing resources to the packaged active count.

    Historical resources beyond the approved count are never deleted.
    They are deactivated only when both the physical resource and its
    corresponding storage unit are unoccupied.
    """
    data = load_data("resources.json")
    company = data.get("company", "الاهدل للبن")
    branch = data.get("branch", "الرئيسي - الاهدل للبن")

    for key, spec in data.items():
        if key in {"company", "branch"}:
            continue

        target_count = int(spec["count"])

        for i in range(1, target_count + 1):
            code = f"{spec['prefix']}-{i:03d}"

            values = {
                "doctype": spec["doctype"],
                "code": code,
                "capacity_kg": spec["capacity_kg"],
                "warehouse": spec["warehouse"],
                "location": code,
                "company": company,
                "branch": branch,
                "status": spec["status"],
                "active": 1,
            }

            if spec.get("bed_type"):
                values["bed_type"] = spec["bed_type"]

            name = frappe.db.exists(spec["doctype"], {"code": code})

            if name:
                doc = frappe.get_doc(spec["doctype"], name)
                changed = False

                for fieldname, value in values.items():
                    if fieldname == "doctype":
                        continue
                    if getattr(doc, fieldname, None) != value:
                        setattr(doc, fieldname, value)
                        changed = True

                if changed:
                    doc.save(ignore_permissions=True)
            else:
                frappe.get_doc(values).insert(ignore_permissions=True)

            unit = frappe.db.get_value(
                "Coffee Storage Unit",
                {"unit_code": code},
                "name",
            )

            if unit:
                current_qty = frappe.db.get_value(
                    "Coffee Storage Unit",
                    unit,
                    "current_qty",
                )

                unit_values = {
                    "storage_type": spec["storage_type"],
                    "capacity_kg": spec["capacity_kg"],
                    "warehouse": spec["warehouse"],
                    "location": code,
                    "company": company,
                    "branch": branch,
                    "status": "Available",
                    "active": 1,
                }

                # Never overwrite an existing quantity during convergence.
                # Quantity belongs to the operational stock/resource state.
                if current_qty is None:
                    unit_values["current_qty"] = 0

                frappe.db.set_value(
                    "Coffee Storage Unit",
                    unit,
                    unit_values,
                    update_modified=False,
                )
            else:
                frappe.get_doc(
                    {
                        "doctype": "Coffee Storage Unit",
                        "unit_code": code,
                        "storage_type": spec["storage_type"],
                        "capacity_kg": spec["capacity_kg"],
                        "warehouse": spec["warehouse"],
                        "location": code,
                        "company": company,
                        "branch": branch,
                        "status": "Available",
                        "active": 1,
                        "current_qty": 0,
                    }
                ).insert(ignore_permissions=True)

        # Keep historical resources but deactivate resources above the
        # approved count. Never deactivate an occupied resource.
        extra_names = frappe.get_all(
            spec["doctype"],
            filters={"code": ["like", f"{spec['prefix']}-%"]},
            pluck="name",
        )

        for resource_name in extra_names:
            code = frappe.db.get_value(
                spec["doctype"],
                resource_name,
                "code",
            )

            if not code:
                continue

            try:
                number = int(code.rsplit("-", 1)[1])
            except (TypeError, ValueError):
                continue

            if number <= target_count:
                continue

            resource_qty = frappe.db.get_value(
                spec["doctype"],
                resource_name,
                "current_qty",
            )

            unit = frappe.db.get_value(
                "Coffee Storage Unit",
                {"unit_code": code},
                "name",
            )

            unit_qty = None
            if unit:
                unit_qty = frappe.db.get_value(
                    "Coffee Storage Unit",
                    unit,
                    "current_qty",
                )

            occupied = max(
                float(resource_qty or 0),
                float(unit_qty or 0),
            )

            if occupied > 0:
                frappe.throw(
                    _(
                        "لا يمكن تعطيل المورد {0} لأنه يحتوي كمية مشغولة {1} كجم."
                    ).format(code, occupied)
                )

            frappe.db.set_value(
                spec["doctype"],
                resource_name,
                {
                    "active": 0,
                    "status": "غير فعال",
                },
                update_modified=False,
            )

            if unit:
                # Do not alter current_qty while deactivating.
                frappe.db.set_value(
                    "Coffee Storage Unit",
                    unit,
                    {
                        "active": 0,
                        "status": "Inactive",
                    },
                    update_modified=False,
                )

def ensure_process_rules():
    """Converge critical operation/route rules after fixture sync."""
    rules = {
        "SORTING": {"allow_multiple_inputs": 1, "requires_quality": 0, "cost_allocation_method": "Same Input Cost"},
        "FERMENTATION": {"allow_multiple_outputs": 1},
        "DRYING": {"allow_multiple_outputs": 1},
    }
    for name, values in rules.items():
        if not frappe.db.exists("Coffee Operation Master", name):
            continue
        frappe.db.set_value("Coffee Operation Master", name, values, update_modified=False)

    for route_name in frappe.get_all("Coffee Process Route", pluck="name"):
        route = frappe.get_doc("Coffee Process Route", route_name)
        for step in route.steps:
            if step.operation == "SORTING":
                step.allow_multiple_inputs = 1
                step.requires_quality = 0
            elif step.operation == "FERMENTATION":
                step.minimum_days = 1
                step.maximum_days = 5
                step.allow_multiple_outputs = 1
            elif step.operation == "DRYING":
                step.minimum_days = 25
                step.maximum_days = 30
                step.allow_multiple_outputs = 1
        route.save(ignore_permissions=True)

def install_master_data():

    """
    Install the complete Coffee Processing master data.

    This function is intentionally idempotent.
    It can safely be executed more than once.
    """

    frappe.flags.in_coffee_master_install = True

    try:
        ensure_uoms()
        ensure_company()
        ensure_currencies()
        ensure_item_groups()
        ensure_accounts()
        ensure_warehouses()
        ensure_cost_centers()
        ensure_items()
        ensure_supplier_fields()
        ensure_supplier_regions()
        ensure_roles()
        ensure_bank_and_wallet_accounts()
        update_company_defaults()
        ensure_process_cost_links()
        ensure_process_rules()
        ensure_coffee_resources()
        remove_legacy_coffee_number_cards()
        ensure_coffee_dashboard()

        frappe.db.commit()

    except Exception:
        frappe.db.rollback()
        raise

    finally:
        frappe.flags.in_coffee_master_install = False


def after_install():
    install_master_data()
