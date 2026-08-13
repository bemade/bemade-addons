# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "Product UoM Packaging",
    "summary": """
        Link products to UoMs with package type for dimensions""",
    "version": "19.0.2.0.2",
    "development_status": "Alpha",
    "license": "LGPL-3",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "maintainers": ["mdurepos"],
    "depends": [
        "product",
        "sale",
        "purchase",
        "stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/product_uom_packaging_views.xml",
        "views/product_product_views.xml",
        "views/sale_order_views.xml",
        "views/purchase_order_views.xml",
        "views/stock_move_views.xml",
        "views/stock_move_line_views.xml",
        "views/stock_picking_views.xml",
        "report/sale_order_templates.xml",
    ],
    "assets": {
        "web.assets_unit_tests": [
            "product_uom_packaging/static/tests/**/*",
            ("remove", "product_uom_packaging/static/tests/tours/**/*"),
        ],
        "web.assets_tests": [
            "product_uom_packaging/static/tests/tours/**/*",
        ],
    },
}
