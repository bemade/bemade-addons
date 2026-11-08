# -*- coding: utf-8 -*-
{
    "name": "Replenish by First Vendor",
    "version": "18.0.0.1.0",
    "category": "Inventory/Inventory",
    "license": "GPL-3",
    "summary": "Keep a vendor on manual replenishment lines and find them by vendor",
    "description": """
    Manual replenishment lines get a vendor: the first current vendor price of
    the product, by sequence (or its first price at all if none is current).
    This happens when the line is created and again whenever the product's
    vendor prices or the line's trigger change, as long as the line has no
    vendor. A vendor already on the line is never replaced. Automatic lines are
    left to Odoo's own choice of vendor.

    On the Replenishment screen, the Vendor column is shown by default, lines
    can be grouped and filtered by their vendor in the left-hand panel, and a
    "Can be bought from" search finds every line whose product has a price from
    a vendor, not only its first one. The plain Vendor search keeps searching
    the line's own vendor.
    """,
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": [
        "stock",
        "purchase",
        "purchase_stock",
    ],
    "data": [
        "views/stock_orderpoint_views.xml",
    ],
    "auto_install": False,
    "installable": True,
}
