# -*- coding: utf-8 -*-
{
    "name": "Bemade Sale Price Rounding",
    "version": "18.0.1.0.0",
    "category": "Sales",
    "summary": "Round sale order line unit prices to currency precision after pricelist computation",
    "description": """
Rounds the unit price on sale order lines to the active currency's precision
after pricelist computation.

Since Odoo 18 (January 2026), price fields use a minimum display precision
rather than a hard precision, meaning pricelist percentage/formula rules can
produce unit prices with 4–6 decimal places. This causes customer-facing
documents to show inconsistent math (e.g. 1.11 × 3 = 3.34 instead of 3.33).
This module restores rounding to the currency precision at computation time.
    """,
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": ["sale"],
    "auto_install": False,
    "installable": True,
    "license": "LGPL-3",
}
