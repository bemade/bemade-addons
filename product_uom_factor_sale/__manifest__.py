# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "Product UoM Factor – Sale Bridge",
    "summary": "Displays the base-UoM equivalent quantity on sale order lines",
    "version": "19.0.1.0.0",
    "development_status": "Alpha",
    "license": "LGPL-3",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "maintainers": ["mdurepos"],
    "depends": [
        "product_uom_factor",
        "sale",
    ],
    "data": [
        "views/sale_order_views.xml",
        "report/sale_order_templates.xml",
    ],
    "assets": {
        "web.assets_unit_tests": [
            "product_uom_factor_sale/static/tests/**/*",
            ("remove", "product_uom_factor_sale/static/tests/tours/**/*"),
        ],
        "web.assets_tests": [
            "product_uom_factor_sale/static/tests/tours/**/*",
        ],
    },
}
