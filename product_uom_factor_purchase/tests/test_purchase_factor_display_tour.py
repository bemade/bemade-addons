# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

"""
Tour test: factor_base_uom_display column visible on a purchase order with a
cross-category factor line.

The JS tour (purchase_factor_display_tour) opens the PO form, waits for the
order_line list to load, then asserts a td[name='factor_base_uom_display']
cell whose text contains '= '.  This confirms the optional "Base UoM" column
is present and populated with the delegated-UoM display value.
"""

from datetime import date

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestPurchaseFactorDisplayTour(HttpCase):
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
            {"name": "BagPOTour", "relative_factor": 1.0}
        )
        uom_lb = cls.env.ref("uom.product_uom_lb")

        product = cls.env["product.product"].create(
            {
                "name": "Tour Powder Purchase",
                "uom_id": uom_lb.id,
                "uom_ids": [(4, uom_lb.id), (4, uom_bag.id)],
                "standard_price": 3.0,
            }
        )
        # 1 BagPOTour = 50 lb: creates a delegate uom.uom in lb's tree.
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

        vendor = cls.env["res.partner"].create(
            {"name": "Tour Vendor Purchase", "supplier_rank": 1}
        )

        # Create a PO with a line in the delegate UoM so the display compute
        # populates and the tour selector finds text containing '= '.
        po = cls.env["purchase.order"].create(
            {
                "partner_id": vendor.id,
                "date_order": date.today(),
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_qty": 3.0,
                            "product_uom_id": delegate_bag.id,
                            "price_unit": 3.0,
                            "date_planned": date.today(),
                            "name": product.name,
                        },
                    )
                ],
            }
        )
        cls.po_id = po.id

    def test_purchase_factor_display_tour(self):
        self.start_tour(
            f"/odoo/purchase/{self.po_id}",
            "purchase_factor_display_tour",
            login="admin",
        )
