"""
Integration tests for product_uom_factor_sale.

Tests cover:
  - Crit 6 (refinement): cross-tree UoM constraint on SO line raises ValidationError
  - Crit 6 (refinement): delegate-mL in factor_base_uom_display compute for SO line
  - Scoping: allowed_uom_ids on SO line contains delegate-mL via product.uom_ids

NOTE: End-to-end SO delivery flow (picking_ids) requires sale_stock.
      Those tests live in product_uom_factor_stock/tests/test_stock_integration.py.
"""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSaleIntegrationBase(TransactionCase):
    """Common fixture for sale integration tests."""

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
                "name": "Test Ink – SO Integration",
                "type": "consu",
                "uom_id": cls.uom_unit.id,
                "list_price": 800.0,
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

        cls.customer = cls.env["res.partner"].create(
            {"name": "Test Ink Customer (SO Integration)", "customer_rank": 1}
        )


class TestSaleLineConstraint(TestSaleIntegrationBase):
    """Crit 6: constraint rejects cross-tree UoM on SO line; delegate passes."""

    def test_delegate_ml_allowed_on_so_line(self):
        """Creating a SO line with delegate-mL does NOT raise ValidationError."""
        so = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.ink.id,
                            "product_uom_qty": 250000.0,
                            "product_uom_id": self.delegate_ml.id,
                            "price_unit": 0.004,
                        },
                    )
                ],
            }
        )
        self.assertEqual(len(so.order_line), 1)
        self.assertEqual(so.order_line.product_uom_id, self.delegate_ml)

    def test_cross_tree_uom_on_so_line_raises_validation_error(self):
        """Generic mL (cross-tree for Unit-base) on SO line raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["sale.order"].create(
                {
                    "partner_id": self.customer.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.ink.id,
                                "product_uom_qty": 250000.0,
                                "product_uom_id": self.uom_ml.id,  # generic mL
                                "price_unit": 0.004,
                            },
                        )
                    ],
                }
            )


class TestSaleLineDisplayCompute(TestSaleIntegrationBase):
    """Crit 6 (display compute): factor_base_uom_display shows correct base UoM qty."""

    def test_factor_base_uom_qty_on_delegate_ml(self):
        """SO line with 250000 delegate-mL: factor_base_uom_qty == 12.5 Unit."""
        so = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.ink.id,
                            "product_uom_qty": 250000.0,
                            "product_uom_id": self.delegate_ml.id,
                            "price_unit": 0.004,
                        },
                    )
                ],
            }
        )
        sol = so.order_line
        # factor_base_uom_qty: 250000 × 0.00005 = 12.5 Unit
        self.assertAlmostEqual(
            sol.factor_base_uom_qty,
            12.5,
            places=4,
            msg="factor_base_uom_qty must be 12.5 Unit (250000 delegate-mL × 0.00005)",
        )

    def test_factor_base_uom_display_empty_for_same_category_uom(self):
        """SO line with a same-category UoM has empty factor_base_uom_display."""
        uom_liter = self.env.ref("uom.product_uom_litre")
        liter_ink = self.env["product.product"].create(
            {
                "name": "Liter Ink – SO (no factor)",
                "type": "consu",
                "uom_id": uom_liter.id,
            }
        )
        so = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": liter_ink.id,
                            "product_uom_qty": 5.0,
                            "product_uom_id": self.uom_ml.id,  # same category
                            "price_unit": 10.0,
                        },
                    )
                ],
            }
        )
        sol = so.order_line
        self.assertEqual(
            sol.factor_base_uom_display,
            "",
            "factor_base_uom_display must be empty when using same-category UoM",
        )
        self.assertAlmostEqual(
            sol.factor_base_uom_qty,
            0.0,
            places=2,
            msg="factor_base_uom_qty must be 0.0 when using same-category UoM",
        )

    def test_delegate_ml_in_so_line_allowed_uom_ids(self):
        """Delegate-mL id is in a SO line's allowed_uom_ids for the ink product.

        Compare via .ids because .new() records return NewId proxies that
        don't compare equal to database record IDs with assertIn().
        """
        so = self.env["sale.order"].create({"partner_id": self.customer.id})
        sol = self.env["sale.order.line"].new(
            {
                "order_id": so.id,
                "product_id": self.ink.id,
                "product_uom_qty": 1.0,
                "product_uom_id": self.uom_unit.id,
                "price_unit": 800.0,
            }
        )
        sol._compute_allowed_uom_ids()
        self.assertIn(
            self.delegate_ml.id,
            sol.allowed_uom_ids.ids,
            "Delegate-mL must be in SO line allowed_uom_ids.ids (via product.uom_ids)",
        )
