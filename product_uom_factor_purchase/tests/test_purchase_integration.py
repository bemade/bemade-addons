"""
Integration tests for product_uom_factor_purchase.

Tests cover:
  - Crit 6 (refinement): cross-tree UoM constraint on PO line raises ValidationError
  - Crit 6 (refinement): delegate-mL in factor_base_uom_display compute for PO line
  - Scoping: allowed_uom_ids on PO line contains delegate-mL via product.uom_ids

NOTE: End-to-end PO receipt flow (picking_ids) requires purchase_stock.
      Those tests live in product_uom_factor_stock/tests/test_stock_integration.py.
"""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestPurchaseIntegrationBase(TransactionCase):
    """Common fixture for purchase integration tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env["res.config.settings"].create({"group_uom": True}).execute()

        dp = cls.env["decimal.precision"].search(
            [("name", "=", "Product Unit")], limit=1
        )
        if dp and dp.digits < 5:
            dp.digits = 5

        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.uom_ml = cls.env.ref("uom.product_uom_milliliter")

        # Ink product: Unit base
        cls.ink = cls.env["product.product"].create(
            {
                "name": "Test Ink – PO Integration",
                "type": "consu",
                "uom_id": cls.uom_unit.id,
                "standard_price": 800.0,
            }
        )

        # Factor: 1 delegate-mL = 0.00005 Unit
        cls.factor = cls.env["product.uom.factor"].create(
            {
                "product_tmpl_id": cls.ink.product_tmpl_id.id,
                "foreign_uom_id": cls.uom_ml.id,
                "factor": 0.00005,
            }
        )
        cls.delegate_ml = cls.factor.delegate_uom_id
        cls.ink.product_tmpl_id.write({"uom_factor_ids": [(4, cls.factor.id)]})

        cls.vendor = cls.env["res.partner"].create(
            {"name": "Test Ink Vendor (PO Integration)", "supplier_rank": 1}
        )


class TestPurchaseLineConstraint(TestPurchaseIntegrationBase):
    """Crit 6: constraint rejects cross-tree UoM on PO line; delegate passes."""

    def test_delegate_ml_allowed_on_po_line(self):
        """Creating a PO line with delegate-mL does NOT raise ValidationError."""
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.ink.id,
                            "product_qty": 250000.0,
                            "product_uom_id": self.delegate_ml.id,
                            "price_unit": 0.004,
                            "name": self.ink.name,
                        },
                    )
                ],
            }
        )
        self.assertEqual(len(po.order_line), 1)
        self.assertEqual(po.order_line.product_uom_id, self.delegate_ml)

    def test_cross_tree_uom_on_po_line_raises_validation_error(self):
        """Generic mL (cross-tree for Unit-base product) on PO line raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["purchase.order"].create(
                {
                    "partner_id": self.vendor.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.ink.id,
                                "product_qty": 250000.0,
                                "product_uom_id": self.uom_ml.id,  # generic mL
                                "price_unit": 0.004,
                                "name": self.ink.name,
                            },
                        )
                    ],
                }
            )


class TestPurchaseLineDisplayCompute(TestPurchaseIntegrationBase):
    """Crit 6 (display compute): factor_base_uom_display shows correct base UoM qty."""

    def test_factor_base_uom_qty_on_delegate_ml(self):
        """PO line with 250000 delegate-mL: factor_base_uom_qty == 12.5 Unit."""
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.ink.id,
                            "product_qty": 250000.0,
                            "product_uom_id": self.delegate_ml.id,
                            "price_unit": 0.004,
                            "name": self.ink.name,
                        },
                    )
                ],
            }
        )
        pol = po.order_line
        # factor_base_uom_qty: 250000 × 0.00005 = 12.5 Unit
        self.assertAlmostEqual(
            pol.factor_base_uom_qty,
            12.5,
            places=4,
            msg="factor_base_uom_qty must be 12.5 Unit (250000 delegate-mL × 0.00005)",
        )

    def test_factor_base_uom_display_empty_for_same_category_uom(self):
        """PO line with a same-category UoM has empty factor_base_uom_display."""
        uom_liter = self.env.ref("uom.product_uom_litre")
        # Create a liter-based product with no factor
        liter_ink = self.env["product.product"].create(
            {
                "name": "Liter Ink (no factor)",
                "type": "consu",
                "uom_id": uom_liter.id,
            }
        )
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": liter_ink.id,
                            "product_qty": 5.0,
                            "product_uom_id": self.uom_ml.id,  # same category
                            "price_unit": 10.0,
                            "name": liter_ink.name,
                        },
                    )
                ],
            }
        )
        pol = po.order_line
        self.assertEqual(
            pol.factor_base_uom_display,
            "",
            "factor_base_uom_display must be empty when using same-category UoM",
        )
        self.assertAlmostEqual(
            pol.factor_base_uom_qty,
            0.0,
            places=2,
            msg="factor_base_uom_qty must be 0.0 when using same-category UoM",
        )

    def test_delegate_ml_in_po_line_allowed_uom_ids(self):
        """Delegate-mL id is in a PO line's allowed_uom_ids for the ink product.

        Compare via .ids because .new() records return NewId proxies that
        don't compare equal to database record IDs with assertIn().
        """
        po = self.env["purchase.order"].create({"partner_id": self.vendor.id})
        pol = self.env["purchase.order.line"].new(
            {
                "order_id": po.id,
                "product_id": self.ink.id,
                "product_qty": 1.0,
                "product_uom_id": self.uom_unit.id,
                "price_unit": 800.0,
                "name": self.ink.name,
            }
        )
        pol._compute_allowed_uom_ids()
        self.assertIn(
            self.delegate_ml.id,
            pol.allowed_uom_ids.ids,
            "Delegate-mL must be in PO line allowed_uom_ids.ids (via product.uom_ids)",
        )
