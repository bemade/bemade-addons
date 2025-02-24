{
    "name": "Reception Purchase Total",
    "version": "18.0.1.0.0",
    "category": "Inventory/Purchase",
    "summary": "Display purchase totals on stock reception views",
    "description": """
This module adds purchase price totals to stock reception views. Specifically:

* Adds a total amount column to stock move lines in receptions, showing the purchase price * quantity
* Shows a total amount at the bottom of operations and detailed operations tabs in:
  - Reception form view
  - Batch Transfer form view
* Links stock moves to their original purchase order line prices

Technical Details:
* Extends stock.move to compute total amount based on purchase line price
* Adds computed fields and view inheritance to display totals
* Compatible with standard Odoo purchase and inventory workflows
    """,
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": [
        "stock",
        "purchase_stock",
    ],
    "data": [
        "views/stock_picking_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "auto_install": False,
    "application": False,
}
