# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

"""
Tour test: factor_base_uom_display column visible on a sale order with a
cross-category factor line.

The JS tour (sale_factor_display_tour) opens the SO form, waits for the
order_line list to load, then asserts a td[name='factor_base_uom_display']
cell whose text contains '= '.  This confirms the optional "Base UoM" column
is present and populated with the delegated-UoM display value.
"""

from datetime import date

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestSaleFactorDisplayTour(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Ensure enough decimal precision for sub-unit quantities (e.g. 0.0125).
        dp = cls.env["decimal.precision"].search(
            [("name", "=", "Product Unit")], limit=1
        )
        if dp and dp.digits < 5:
            dp.digits = 5

        # Stand-alone root UoM: no relative_uom_id → cross-category w.r.t. lb/kg.
        uom_bag = cls.env["uom.uom"].create(
            {"name": "BagSaleTour", "relative_factor": 1.0}
        )
        uom_lb = cls.env.ref("uom.product_uom_lb")

        product = cls.env["product.product"].create(
            {
                "name": "Tour Powder Sale",
                "uom_id": uom_lb.id,
                "uom_ids": [(4, uom_lb.id), (4, uom_bag.id)],
                "list_price": 5.0,
            }
        )
        # 1 BagSaleTour = 50 lb: creates a delegate uom.uom in lb's tree.
        factor = cls.env["product.uom.factor"].create(
            {
                "product_tmpl_id": product.product_tmpl_id.id,
                "foreign_uom_id": uom_bag.id,
                "factor": 50.0,
            }
        )
        # Trigger additive uom_ids sync so the delegate is selectable on lines.
        product.product_tmpl_id.write({"uom_factor_ids": [(4, factor.id)]})
        delegate_bag = factor.delegate_uom_id

        customer = cls.env["res.partner"].create(
            {"name": "Tour Customer Sale", "customer_rank": 1}
        )

        # Create a confirmed SO with a line in the delegate UoM so the display
        # compute populates and the tour selector finds text containing '= '.
        so = cls.env["sale.order"].create(
            {
                "partner_id": customer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 5.0,
                            "product_uom_id": delegate_bag.id,
                            "price_unit": 5.0,
                        },
                    )
                ],
            }
        )
        cls.so_id = so.id

    def test_sale_factor_display_tour(self):
        self.start_tour(
            f"/odoo/sales/{self.so_id}",
            "sale_factor_display_tour",
            login="admin",
        )
