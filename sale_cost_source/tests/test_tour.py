# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: a salesperson sees the badge, the header summary and the tooltip.

ACCEPTANCE CRITERIA
1. Opening a quotation shows the line's badge and the header summary.
2. Hovering the unit price opens a tooltip listing the evidence.
"""
from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestSaleCostSourceTour(HttpCase):
    def test_tooltip_tour(self):
        product = self.env["product.product"].create(
            {"name": "Tour Component", "type": "consu", "is_storable": True}
        )
        partner = self.env["res.partner"].create({"name": "Tour Customer"})
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [Command.create({"product_id": product.id, "product_uom_qty": 3})],
            }
        )
        self.start_tour(f"/odoo/sales/{order.id}", "sale_cost_source_tooltip", login="admin")
