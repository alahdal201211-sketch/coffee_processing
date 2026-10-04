# -*- coding: utf-8 -*-
import frappe

def daily():
    from coffee_processing.coffee_processing.services.processing_service import check_open_processing_orders
    return check_open_processing_orders()
