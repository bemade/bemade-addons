#
#    Bemade Inc.
#
#    Copyright (C) September 2023 Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is free software: you can redistribute it and/or modify it under the terms of the
#    GNU Lesser General Public License as published by the Free Software Foundation, version 3 (LGPL-3).
#    See https://www.gnu.org/licenses/lgpl-3.0.html.
#
{
    "name": "Sales Margin on Vendor Price",
    "version": "19.0.0.0.8",
    "summary": "Enables calculation of sales margins based on vendor pricelists.",
    "description": """Adds a new method for calculating """,
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "sale_stock_margin",
        "sale_management",
        "stock",
        "product_pricelist_supplierinfo",
    ],
    "data": ["views/sale_order.xml"],
    "installable": True,
    "auto_install": False,
}
