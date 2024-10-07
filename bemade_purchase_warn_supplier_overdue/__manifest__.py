{
    "name": "Bemade Warn Supplier Overdue",
    "version": "1.0",
    "summary": "Warn supplier when overdue on purchase order confirmation",
    "description": """
Warn supplier when overdue on purchase order confirmation
=========================================================
This module adds a mail.activity to the purchase order confirmation form when the supplier is overdue.
""",
    "author": "Benoît Vézina",
    "website": "https://www.bemade.org",
    "category": "Purchases",
    "license": "LGPL-3",
    "depends": [
        "purchase",
        "account",
        "mail",
    ],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
