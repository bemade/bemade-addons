# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "Packaging Quantity Entry",
    "summary": "Make package quantity the driver on PO and SO lines",
    "description": """
Packaging Quantity Entry
========================

Extends ``product_uom_packaging`` so that the **package count is the primary
quantity entered** on both purchase and sale order lines.

When a packaging is selected on a line, the user types how many packages they
want (``product_packaging_qty``). The base stocking-UoM quantity
(``product_qty`` on PO, ``product_uom_qty`` on SO) is derived automatically
via the stored inverse: ``base = pkg_qty × packaging.qty`` converted to the
line UoM.

The forward compute (base → packages, ``ceil``) is retained so the package
column accurately reflects reality when the base qty is edited directly.

View changes: the packaging columns (packaging type + package qty) are moved
**before** the base qty column so the natural entry order is
packaging → packages → (optional) base qty.
""",
    "version": "19.0.1.0.0",
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
