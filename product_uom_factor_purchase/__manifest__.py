# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "Product UoM Factor – Purchase Bridge",
    "summary": "Displays the base-UoM equivalent quantity on purchase order lines",
    "version": "19.0.1.0.0",
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
        "web.assets_unit_tests": [
            "product_uom_factor_purchase/static/tests/**/*",
            ("remove", "product_uom_factor_purchase/static/tests/tours/**/*"),
        ],
        "web.assets_tests": [
            "product_uom_factor_purchase/static/tests/tours/**/*",
        ],
    },
}
