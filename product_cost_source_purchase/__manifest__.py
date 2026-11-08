# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
{
    "name": "Product Cost Source - Purchase History",
    "version": "19.0.1.0.0",
    "summary": "Use confirmed purchase orders and open requests for quotation "
    "as evidence of what a product costs.",
    "description": """Product Cost Source - Purchase History
======================================

*Product Cost Source* judges a price by when it was last established. Supplier
price entries are rarely dated, so on their own they mostly read "Estimated,
undated". A confirmed purchase is the most reliable repricing event there is:
we paid that price, on that day. This module feeds that evidence to the engine.

Confirmed purchases
-------------------

The latest confirmed purchase order line for the product variant, in the
company the cost is resolved for, is a dated price:

* within the price-age setting (6 months by default) it reads
  *Firm. Last purchased 10/02/2026.*
* past it, *Estimated. Last purchased 01/15/2025, over 6 months ago. No
  contract in force.*

The engine keeps whichever is more recent of this purchase and a dated supplier
price; a vendor price list in force (with an end date) still outranks both.
The price is the discounted unit price, converted to the product's unit of
measure and to the requested currency at the purchase date. Cancelled orders,
other companies and other variants are ignored, as are lines priced at zero.

Open requests for quotation
---------------------------

A request for quotation (draft or sent) with a unit price is a price a vendor
quoted that nobody confirmed yet. It is reported at the **Indicative** level:
*Indicative. Quoted $12.50 on RFQ P00042, not yet confirmed.*

It is used only when no firm evidence exists. When a firm price exists and the
RFQ is newer, the RFQ is shown as a note beside the firm price.

Access
------

The purchase history is read with elevated rights, limited to the product and
the company asked about, so a salesperson without Purchase access still gets
the evidence (only the date, price and order number are used).
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "category": "Inventory/Purchase",
    "depends": ["product_cost_source", "purchase"],
    "data": [],
    "installable": True,
    "auto_install": False,
}
