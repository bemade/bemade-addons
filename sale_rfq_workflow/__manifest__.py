{
    'name': 'Sale RFQ Workflow',
    'version': '19.0.1.0.0',
    'category': 'Sales/Purchase',
    'license': 'LGPL-3',
    'author': 'Bemade Inc.',
    'website': 'https://www.bemade.org',
    'depends': ['sale_management', 'purchase_stock', 'sale_purchase_stock'],
    'description': """
Sale RFQ Workflow
=================

Quote-first procurement for resale flows: generate vendor RFQs from a Sales
Order, get vendor pricing on them, and keep those same RFQs as the purchase
documents when the Sales Order is confirmed.

- **Generate RFQs from a Sales Order** via a guided wizard that groups SO
  lines by primary vendor, prompts for vendor assignment on any unassigned
  products (saving the vendor to the product's supplier info), and previews
  the grouping before confirming. Generated RFQ lines are linked to their
  source SO lines (both through ``supply_so_line_id`` and through the core
  ``sale_line_id``).

- **Procurement adoption on SO confirmation.** Core replenishment normally
  matches only *draft* purchase orders, so an RFQ that has been sent to the
  vendor (i.e. exactly the one that has been quoted) gets bypassed and a
  brand-new RFQ is created from supplier-info pricing — losing the vendor
  communication thread. This module makes the buy rule adopt the linked
  supply RFQ instead, in ``draft``, ``sent`` or ``purchase`` state:

  - the human-chosen vendor grouping wins over automatic seller selection,
  - quantities already covered by the RFQ are not doubled (an SO quantity
    increase still procures the difference),
  - a quoted unit price on the RFQ line is never overwritten by the
    supplier-info price.

Sales Orders without linked supply RFQs use the standard flow, untouched.
    """,
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'wizard/rfq_generate_wizard_views.xml',
    ],
    'post_init_hook': '_backfill_sale_line_id',
    'installable': True,
    'auto_install': False,
    'application': False,
}
