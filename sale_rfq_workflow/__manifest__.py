{
    "name": "Sales RFQ Workflow",
    "version": "19.0.1.0.0",
    "category": "Sales/Purchase",
    "license": "LGPL-3",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "summary": "Generate supply RFQs from a Sales Order and adopt them on confirm.",
    "description": """
Sales RFQ Workflow
==================

Generic material-procurement bridge between Sales and Purchase:

- **Generate RFQs from a Sales Order** via a guided wizard that groups SO lines
  by primary vendor, prompts for a vendor on any unassigned product (saving the
  choice to the product's supplier info), and previews the grouping before
  creating one RFQ per vendor. Each created RFQ line is linked back to its
  source SO line (both the bespoke ``supply_so_line_id`` and the core
  ``sale_line_id``) so the procurement engine recognises the RFQ as covering the
  SO demand.

- **Adoption on confirm.** When a Sales Order whose demand is already covered by
  a wizard-generated supply RFQ is confirmed, the buy procurement adopts that
  RFQ — including quoted (``sent``) and confirmed (``purchase``) ones — instead
  of spinning up a duplicate Purchase Order. Quantities are not doubled, the
  buyer's vendor grouping and negotiated prices are preserved, and receipts are
  threaded into the SO delivery chain. Later quantity increases still procure
  only the delta.

This module carries no pricing or markup policy; it only wires the SO/RFQ link
and the procurement adoption.
    """,
    "depends": [
        "sale_management",
        "purchase_stock",
        "sale_purchase_stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/sale_order_views.xml",
        "views/purchase_order_views.xml",
        "wizard/rfq_generate_wizard_views.xml",
    ],
    "post_init_hook": "_backfill_supply_sale_line",
    "installable": True,
    "auto_install": False,
    "application": False,
}
