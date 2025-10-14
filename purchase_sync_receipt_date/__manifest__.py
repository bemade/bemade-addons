# Copyright 2025 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

{
    "name": "Purchase Sync Receipt Date",
    "version": "18.0.1.0.0",
    "category": "Purchases",
    "summary": "Synchronize receipt scheduled dates with purchase order expected dates",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "purchase_stock",
    ],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
}
