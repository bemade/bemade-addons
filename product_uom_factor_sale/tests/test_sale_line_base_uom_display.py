"""
Tests for product_uom_factor_sale: computed base-UoM display fields on SO lines.

Acceptance Criteria:
1. Happy path: 5 Bag × 50 lb/Bag → factor_base_uom_qty=250.0,
   factor_base_uom_display="= 250.00 lb".
2. Same-category no-op: line UoM == product base UoM → factor_base_uom_qty=0.0.
3. Missing factor no-op: no product.uom.factor row for the cross-category UoM
   → factor_base_uom_qty=0.0 (does not raise).
"""

from odoo.tests.common import TransactionCase


class TestSaleLineBaseUomDisplay(TransactionCase):
    """Test computed base-UoM display fields on sale.order.line."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom_lb = cls.env.ref("uom.product_uom_lb")
        cls.uom_kg = cls.env.ref("uom.product_uom_kgm")

        # "Bag" is a standalone root UoM (no relative_uom_id) so it has no
        # common reference with any weight/volume UoM — i.e. it is cross-category
        # relative to lb/kg in the Odoo 19 tree-based UoM model.
        cls.uom_bag = cls.env["uom.uom"].create(
            {
                "name": "Bag",
                "relative_factor": 1.0,
            }
        )

        cls.customer = cls.env["res.partner"].create(
            {"name": "Test Customer", "customer_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Powder",
                "uom_id": cls.uom_lb.id,
                "uom_ids": [(4, cls.uom_lb.id), (4, cls.uom_bag.id)],
                "list_price": 5.0,
            }
        )
        # 1 Bag = 50 lb
        cls.factor = cls.env["product.uom.factor"].create(
            {
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "uom_id": cls.uom_bag.id,
                "factor": 50.0,
            }
        )

    def _make_so_line(self, qty, uom):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": qty,
                            "product_uom_id": uom.id,
                            "price_unit": 5.0,
                        },
                    )
                ],
            }
        )
        return so.order_line

    def test_happy_path_cross_category(self):
        """5 Bag × 50 lb/Bag → factor_base_uom_qty=250.0, display='= 250.00 lb'."""
        line = self._make_so_line(5.0, self.uom_bag)
        self.assertAlmostEqual(line.factor_base_uom_qty, 250.0, places=2)
        self.assertEqual(line.factor_base_uom_display, "= 250.00 lb")

    def test_same_category_no_display(self):
        """Line UoM in the same category as base UoM → qty=0.0, no display."""
        line = self._make_so_line(10.0, self.uom_lb)
        self.assertEqual(line.factor_base_uom_qty, 0.0)
        self.assertEqual(line.factor_base_uom_display, "")

    def test_same_category_kg_no_display(self):
        """Line UoM kg (same weight category as lb) → qty=0.0."""
        line = self._make_so_line(2.0, self.uom_kg)
        self.assertEqual(line.factor_base_uom_qty, 0.0)
        self.assertEqual(line.factor_base_uom_display, "")

    def test_missing_factor_no_display(self):
        """Cross-category UoM with no product.uom.factor row → qty=0.0."""
        uom_liter = self.env.ref("uom.product_uom_litre")
        # Product has no factor for litre; this should not raise.
        product2 = self.env["product.product"].create(
            {
                "name": "Test Powder No Factor",
                "uom_id": self.uom_lb.id,
                "list_price": 5.0,
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
                            "product_id": product2.id,
                            "product_uom_qty": 3.0,
                            "product_uom_id": uom_liter.id,
                            "price_unit": 5.0,
                        },
                    )
                ],
            }
        )
        line = so.order_line
        self.assertEqual(line.factor_base_uom_qty, 0.0)
        self.assertEqual(line.factor_base_uom_display, "")
