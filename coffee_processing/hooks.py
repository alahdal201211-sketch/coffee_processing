app_name = "coffee_processing"

app_title = "Coffee Processing"

app_publisher = "Coffee Processing"

app_description = "Coffee processing and grade traceability"

app_icon = "fa fa-coffee"
app_color = "#6F4E37"
app_logo_url = "/assets/coffee_processing/images/coffee_processing_logo.svg"


add_to_apps_screen = [{
    "name": "coffee_processing",
    "logo": "/assets/coffee_processing/images/coffee_processing_logo.svg",
    "title": "معالجة البن",
    "route": "/app/إدارة-معالجة-البن",
}]


app_email = ""

app_license = "MIT"


fixtures = [

    # ==========================
    # Coffee Master Data
    # ==========================

    {
        "dt": "Coffee Operation Master",
        "filters": []
    },

    {
        "dt": "Coffee Process Route",
        "filters": []
    },

    {
        "dt": "Coffee Grade Master",
        "filters": []
    },


    # ==========================
    # Company Branding
    # ==========================

    {
        "dt": "Letter Head",
        "filters": [
            ["name", "=", "ALC Coffee Letter Head"]
        ]
    },


    # ==========================
    # Coffee Print Formats
    # ==========================

    {
        "dt": "Print Format",
        "filters": [
            ["name", "=", "Coffee Process Order Arabic"]
        ]
    },


    # ==========================
    # Workspace
    # ==========================

    {
        "dt": "Workspace",
        "filters": [
            ["name", "=", "إدارة معالجة البن"]
        ]
    },


    {
        "dt": "Number Card",
        "filters": [
            ["module", "=", "Coffee Processing"]
        ]
    },


    {
        "dt": "Report",
        "filters": [
            ["module", "=", "Coffee Processing"]
        ]
    },


    # ==========================
    # Customizations
    # ==========================

    {
        "dt": "Custom Field",
        "filters": [
            ["dt", "=", "Supplier"],
            ["fieldname", "=", "region"]
        ]
    },


    {
        "dt": "Client Script",
        "filters": [
            ["dt", "=", "Supplier"],
            ["name", "=", "Supplier Region Country Filter"]
        ]
    },
]



# ==========================
# Purchase Receipt Automation
# ==========================

doc_events = {
    "Purchase Receipt": {
        "on_submit": (
            "coffee_processing.coffee_processing.services."
            "purchase_receipt_service.on_purchase_receipt_submit"
        ),
        "on_cancel": (
            "coffee_processing.coffee_processing.services."
            "purchase_receipt_service.on_purchase_receipt_cancel"
        ),
    }
}


app_modules = [
    "coffee_processing"
]


override_doctype_class = {
    "Coffee Process Order":
        "coffee_processing.coffee_processing.doctype.coffee_process_order.coffee_process_order.CoffeeProcessOrder"
}


after_install = "coffee_processing.setup.install.after_install"


# Re-apply idempotent master data after migrations
# so new sites and upgrades converge.

after_migrate = "coffee_processing.setup.install.install_master_data"