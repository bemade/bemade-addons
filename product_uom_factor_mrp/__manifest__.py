# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "Product UoM Factor – MRP",
    "summary": "BOM line UoM scoping for product-specific cross-category factors",
    "version": "19.0.2.0.0",
    "development_status": "Alpha",
    "license": "LGPL-3",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "maintainers": ["mdurepos"],
    "depends": [
        "product_uom_factor",
        "mrp",
    ],
    "data": [
        "views/mrp_bom_views.xml",
    ],
}
