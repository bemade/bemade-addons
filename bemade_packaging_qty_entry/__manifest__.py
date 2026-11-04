# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "Packaging Quantity Entry",
    "summary": "Make package quantity the driver on PO and SO lines",
    "version": "19.0.1.0.1",
    "development_status": "Alpha",
    "license": "LGPL-3",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "maintainers": ["mdurepos"],
    "depends": ["product_uom_packaging"],
    "data": [
        "views/purchase_order_views.xml",
        "views/sale_order_views.xml",
    ],
}
