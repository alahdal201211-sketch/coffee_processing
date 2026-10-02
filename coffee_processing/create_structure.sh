#!/bin/bash
set -e

APP_PATH="$HOME/frappe-bench/apps/coffee_processing"
CP="$APP_PATH/coffee_processing"

mkdir -p "$APP_PATH/translations"
mkdir -p "$APP_PATH/fixtures"
mkdir -p "$APP_PATH/patches/v1_0"
# Legacy dashboard directory intentionally removed; dashboard is managed by setup/install.py
mkdir -p "$CP/doctype"
mkdir -p "$CP/services"
mkdir -p "$CP/validations"
mkdir -p "$CP/api"
mkdir -p "$CP/report/grade_wise_stock"
mkdir -p "$CP/report/grade_wise_cost"
mkdir -p "$CP/report/grade_wise_sales"
mkdir -p "$CP/report/grade_wise_profitability"
mkdir -p "$CP/report/grade_yield"

touch "$APP_PATH/tasks.py"
touch "$APP_PATH/permissions.py"
touch "$APP_PATH/translations/ar.csv"
touch "$APP_PATH/patches/__init__.py"
touch "$APP_PATH/patches/v1_0/__init__.py"
touch "$APP_PATH/patches/v1_0/create_roles.py"

touch "$CP/doctype/__init__.py"
touch "$CP/services/__init__.py"
touch "$CP/validations/__init__.py"
touch "$CP/api/__init__.py"

create_doctype() {
    local name="$1"
    local has_js="$2"
    local dir="$CP/doctype/$name"
    mkdir -p "$dir"
    touch "$dir/__init__.py"
    touch "$dir/$name.json"
    touch "$dir/$name.py"
    [ "$has_js" = "1" ] && touch "$dir/$name.js"
}

create_doctype "coffee_operation_master" 1
create_doctype "coffee_process_route" 1
create_doctype "coffee_process_route_step" 0
create_doctype "coffee_grade_master" 1
create_doctype "coffee_cost_center_mapping" 1
create_doctype "coffee_processing_input" 0
create_doctype "coffee_processing_output" 0
create_doctype "coffee_daily_monitoring" 0
create_doctype "coffee_blend_source" 0
create_doctype "coffee_batch" 1
create_doctype "coffee_processing_order" 1
create_doctype "coffee_sample" 1
create_doctype "coffee_cupping" 1
create_doctype "coffee_blend_order" 1
create_doctype "coffee_packaging_order" 1
create_doctype "coffee_route_change_log" 1

echo "✓ الهيكل جاهز: $APP_PATH"
