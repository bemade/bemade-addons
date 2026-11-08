# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
{
    "name": "Sale Cost Source",
    "version": "19.0.1.0.0",
    "summary": "Show on each quotation line how reliable its cost is (firm, "
    "indicative, estimated, unknown) and why.",
    "description": """Sale Cost Source
================

A quotation is only as good as the costs behind it. This module shows sales
staff, on every quotation and order line, how far the cost of that line can be
trusted, using the evidence resolved by *Product Cost Source*.

On each line
------------

* A **badge** -- Firm, Indicative, Estimated or Unknown -- in an optional
  column after the subtotal, and in the line form.
* A **one-line reason** naming the evidence, e.g. *Firm. Vendor price list
  valid to 11/30/2026.* or *Estimated. Last known price 01/03/2025, over 6
  months old. No contract in force.* When the vendor price expires before the
  line's delivery date (the order's commitment date, else its expected date),
  the reason ends with a warning.
* A **tooltip on the unit price** listing the evidence, warnings and notes
  for that line.

Free stock in the order's warehouse covers the line first, at stock valuation;
lines of the same product on one order share that stock. Services,
non-storable products, sections, notes and lines with a quantity of zero or
less carry no indicator.

On the order
------------

A badge next to the totals sums up the lines that are not firm, worst first,
e.g. *2 lines Unknown, 1 line Estimated*. It is hidden when every line is
firm.

What it does not do
-------------------

Nothing is stored and nothing is blocked: the indicator is computed each time
the order is displayed, with today's prices and stock, and no price is ever
changed. It is visible to the salesman group only, and appears neither on the
printed quotation nor on the customer portal.

Install *Product Cost Source - Purchase History* as well to use purchase
orders and open requests for quotation as evidence.
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "category": "Sales/Sales",
    "depends": ["sale_stock", "product_cost_source"],
    "data": ["views/sale_order_views.xml"],
    "assets": {
        "web.assets_backend": [
            "sale_cost_source/static/src/cost_source_price/*",
        ],
        "web.assets_tests": [
            "sale_cost_source/static/tests/tours/*.js",
        ],
    },
    "installable": True,
    "auto_install": False,
}
