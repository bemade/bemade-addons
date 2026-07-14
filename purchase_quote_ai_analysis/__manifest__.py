{
    'name': 'Purchase Quote AI Analysis',
    'version': '19.0.1.0.1',
    'category': 'Inventory/Purchase',
    'license': 'LGPL-3',
    'author': 'Bemade Inc.',
    'website': 'https://www.bemade.org',
    'depends': ['purchase'],
    'description': """
Purchase Quote AI Analysis
==========================

Analyse a vendor's quote against an RFQ: upload or paste the quote, let
DeepSeek parse the line items, then review and apply.

- **Price apply**: quoted net unit prices (after any discount) are written to
  the RFQ lines — rounded to the Product Price precision — and to the
  product's supplier info for that vendor.

- **Landed costs on the purchase order**: detected freight/handling/surcharge
  amounts are added as service lines on the RFQ itself, so the RFQ total
  matches the vendor quote. Re-analysing is idempotent — existing fee lines
  (including manually added ones) are updated in place, never duplicated.
  A landed cost left unmapped while marked to apply raises an error instead
  of being silently dropped.

- **Discrepancy review**: products missing from the quote, extra quote lines,
  and quantity mismatches are surfaced before anything is applied.

- **Total sanity check**: when the quote's untaxed total can be extracted, it
  is compared to the RFQ total after apply and the difference is posted to
  the RFQ chatter.

Extension hook: ``_post_apply_landed_costs`` runs after fee lines are applied,
letting downstream modules mirror the charges elsewhere (e.g. onto a linked
sales order).

Setup
-----
Set the DeepSeek API key under Settings → Technical → System Parameters:
key ``purchase_quote_ai_analysis.deepseek_api_key``.

For PDF quote uploads, install ``pypdf`` in the Odoo virtualenv::

    pip install pypdf
    """,
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_order_views.xml',
        'wizard/quote_analysis_wizard_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
