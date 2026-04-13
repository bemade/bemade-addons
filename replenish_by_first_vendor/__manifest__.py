# -*- coding: utf-8 -*-
{
    "name": "Replenish by First Vendor",
    "version": "18.0.0.0.1",
    "category": "Inventory/Inventory",
    "license": "GPL-3",
    "summary": "Auto-select first vendor when creating manual orderpoints",
    "description": """
    Automatically selects the first vendor from a product's vendor list (vendor pricelists)
    when an orderpoint with manual trigger is created, if no vendor is already set.
    
    This helps streamline the orderpoint creation process by automatically setting
    the most relevant vendor based on the product's supplier information.
    """,
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": [
        "stock",
        "purchase",
        "purchase_stock",
    ],
    "data": [],
    "auto_install": False,
    "installable": True,
}
