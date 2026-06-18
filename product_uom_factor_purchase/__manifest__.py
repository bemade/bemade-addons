# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "Product UoM Factor – Purchase",
    "summary": "Base-UoM display on purchase order lines for cross-category factor products",
    "version": "19.0.2.0.0",
    "development_status": "Alpha",
    "license": "LGPL-3",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "maintainers": ["mdurepos"],
    "depends": [
        "product_uom_factor",
        "purchase",
    ],
    "data": [
        "views/purchase_order_views.xml",
        "report/purchase_order_templates.xml",
    ],
    "assets": {
        "web.assets_tests": [
            "product_uom_factor_purchase/static/tests/tours/purchase_factor_display_tour.js",
        ],
    },
}
