{
    "name": "Purchase Quote AI Analysis",
    "version": "19.0.1.0.0",
    "category": "Purchases",
    "license": "LGPL-3",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "summary": "Parse a vendor quote with AI and apply prices and landed-cost "
               "fee lines to the RFQ.",
    "description": """
Purchase Quote AI Analysis
=========================

AI-assisted vendor-quote analysis for a Request for Quotation:

- **Analyse a quote** attached to (or pasted onto) an RFQ: DeepSeek parses the
  line items (French or English, net-of-discount pricing), matches them to the
  RFQ lines by SKU/description, and surfaces any discrepancies (missing, extra,
  quantity mismatch).

- **Apply prices** to the RFQ lines (rounded to the Product Price precision) and
  update the vendor's supplier info.

- **Landed costs on the RFQ.** Freight/handling/duty charges the quote lists
  outside the product lines are mapped to a service product and added to the
  RFQ as fee lines so the RFQ total matches the vendor quote. Fee lines are
  deduped by product (re-analysis updates in place), an applied-but-unmapped
  cost raises, and a vendor-total-vs-RFQ-total sanity note is posted.

An after-apply hook, ``purchase.order._post_apply_landed_costs(fee_lines)``,
lets a downstream module react to the created fee lines (e.g. mirror them onto a
linked Sales Order). This module carries no such policy itself.

Setup
-----
Set the DeepSeek API key under Settings → Technical → System Parameters:
key ``purchase_quote_ai_analysis.deepseek_api_key`` (the legacy
``fitcrew_supply_workflow.deepseek_api_key`` is still read as a fallback).

For PDF quote uploads, install ``pypdf`` in the Odoo virtualenv::

    pip install pypdf
    """,
    "depends": [
        "purchase",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/purchase_order_views.xml",
        "wizard/quote_analysis_wizard_views.xml",
    ],
    "external_dependencies": {"python": ["requests"]},
    "installable": True,
    "auto_install": False,
    "application": False,
}
