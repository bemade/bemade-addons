{
    "name": "Sale Order Show Delivery Address",
    "version": "18.0.1.0.0",
    "category": "Sales",
    "summary": "Show delivery address on sales orders",
    "description": """
This module shows the delivery address on sales orders.
""",
    "author": "Bemade Inc",
    "website": "https://bemade.org",
    "depends": [
        "sale",  # For portal templates and base functionality
    ],
    "data": [
        "views/sale_order_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
