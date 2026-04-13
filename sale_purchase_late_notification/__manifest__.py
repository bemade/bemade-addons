{
    "name": "Sale & Purchase Late Order Notifications",
    "version": "18.0.1.0.0",
    "category": "Sales/Purchases",
    "summary": "Get notifications for late sale and purchase orders",
    "description": """
        This module adds functionality to notify users about late sale and purchase orders.
        It creates activities for orders that are more than 5 days late.
    """,
    "author": "Bemade",
    "website": "https://www.bemade.org",
    "depends": [
        "purchase",
        "sale",
        "mail",
    ],
    "data": [
        "views/sale_views.xml",
        "views/purchase_views.xml",
        "views/res_config_settings_views.xml",
        "views/res_partner_views.xml",
        "data/ir_cron.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
