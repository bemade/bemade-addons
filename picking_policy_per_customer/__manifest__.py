{
    "name": "Customer Specific Picking Policy",
    "version": "19.0.1.0.0",
    "category": "Sales",
    "summary": "Configure picking policy (delivery orders) per customer",
    "description": """
        This module allows you to set specific picking policies per customer.
        It extends the default global picking policy setting to be configurable at the customer level.
    """,
    "author": "Bemade",
    "website": "https://bemade.org",
    "depends": [
        "sale",
        "stock",
    ],
    "data": [
        "views/res_partner_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "auto_install": False,
    "application": False,
}
