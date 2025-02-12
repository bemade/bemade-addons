{
    "name": "Mandatory Customer Reference on Sales Orders",
    "version": "18.0.1.0.0",
    "category": "Sales",
    "summary": "Enforce customer reference on sales orders with portal integration",
    "description": """
This module enforces the requirement of a customer reference (purchase order number) on sales orders before confirmation.
It provides the following features:

* Prevents confirmation of sales orders without a customer reference
* Allows customers to set their reference number through the portal
* Automatically sets reference to "Credit Card" for online payments
* Integrates with both backend and portal interfaces
* Compatible with e-commerce flows
""",
    "author": "Bemade Inc",
    "website": "https://bemade.org",
    "depends": [
        "sale",  # For portal templates and base functionality
        "portal",  # For portal features
        "payment",  # For payment integration
        "website",  # For frontend assets and portal templates
        "website_sale",  # For sale portal features
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/portal_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "sale_mandatory_customer_reference/static/src/js/portal_sale.js",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
