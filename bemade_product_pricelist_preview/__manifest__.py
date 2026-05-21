# -*- coding: utf-8 -*-
{
    "name": "Bemade Product Pricelist Preview",
    "version": "19.0.1.0.0",
    "category": "Product",
    "summary": "Show computed prices across all pricelists on the product Prices tab",
    "description": """
Bemade Product Pricelist Preview
=================================

Extends the **Prices** tab on the product template and product variant forms to
show a second, read-only list of every active sales-channel pricelist that
returns a computed price for the product at qty = 1.0 in its base unit of
measure.

Unlike the standard ``pricelist_rule_ids`` list (which only shows rules that are
explicitly linked to the product), this section includes prices derived from:

- Global fallback rules
- Product-category rules
- Formula-based rules
- Direct product/variant rules

A cap of 100 pricelists per load is applied for performance. If more than 100
active pricelists match, the first 100 (ordered by sequence, then name) are
shown and a warning is logged once per request.

**Sales-channel filter heuristic:** The MVP includes *all* active pricelists
visible to the current company (own-company or shared). Purchase-only filtering
can be opted in by overriding ``_bemade_get_preview_pricelists`` in a downstream
module.

**Variant vs template:** The template form computes prices by passing the
template record to ``_compute_price_rule``; variant-targeted rules may not
surface there. Open the variant form to see variant-only rules.

**Performance note:** Computation runs only when the product form is opened
(never in list/kanban context). Each pricelist triggers one database search
(``_get_applicable_rules``), so worst-case latency scales with the number of
active pricelists but remains sub-second at typical volume (< 50 pricelists).
    """,
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": ["product"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_views.xml",
    ],
    "auto_install": False,
    "installable": True,
    "license": "LGPL-3",
}
