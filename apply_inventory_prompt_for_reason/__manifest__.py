{
    "name": "Stock Quant Apply Single Inventory with Reason",
    "version": "18.0.1.0.0",
    "category": "Inventory/Inventory",
    "summary": "Add reason dialog when applying single inventory adjustment",
    "description": """
This module modifies the behavior of the Apply button on stock quants to show
the same reason dialog as when using Apply All, ensuring consistency in 
inventory adjustment tracking.
    """,
    "author": "Bemade",
    "website": "https://bemade.org",
    "depends": ["stock"],
    "data": [
        "views/stock_quant_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
