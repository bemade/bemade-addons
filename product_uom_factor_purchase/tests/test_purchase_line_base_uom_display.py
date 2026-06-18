"""
Tests for product_uom_factor_purchase: computed base-UoM display on PO lines.

Acceptance Criteria:
1. Happy path: 3 Bag × 50 lb/Bag → factor_base_uom_qty=150.0,
   factor_base_uom_display="= 150.00 lb".
2. Same-category no-op: line UoM == product base UoM → factor_base_uom_qty=0.0.
3. Missing factor no-op: no product.uom.factor row → factor_base_uom_qty=0.0.
"""

from datetime import date

from odoo.tests.common import TransactionCase


class TestPurchaseLineBaseUomDisplay(TransactionCase):
    """Test computed base-UoM display fields on purchase.order.line."""

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
                "name": "BagPO",
                "relative_factor": 1.0,
            }
        )

        cls.vendor = cls.env["res.partner"].create(
            {"name": "Test Vendor PO", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Powder PO",
                "uom_id": cls.uom_lb.id,
                "uom_ids": [(4, cls.uom_lb.id), (4, cls.uom_bag.id)],
                "standard_price": 3.0,
            }
        )
        # 1 Bag = 50 lb. Creating the factor auto-creates a delegate uom.uom
        # (relative_uom_id=lb, relative_factor=50, name="BagPO") in lb's tree.
        # The line must use this delegate, not the generic root Bag.
        cls.factor = cls.env["product.uom.factor"].create(
            {
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "foreign_uom_id": cls.uom_bag.id,
                "factor": 50.0,
            }
        )
        cls.delegate_bag = cls.factor.delegate_uom_id
        cls.product.product_tmpl_id.write(
            {"uom_factor_ids": [(4, cls.factor.id)]}
        )

    def _make_po_line(self, qty, uom):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "date_order": date.today(),
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": qty,
                            "product_uom_id": uom.id,
                            "price_unit": 3.0,
                            "date_planned": date.today(),
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )
        return po.order_line

    def test_happy_path_cross_category(self):
        """3 Bag × 50 lb/Bag → factor_base_uom_qty=150.0, display='= 150.00 lb'."""
        line = self._make_po_line(3.0, self.delegate_bag)
        self.assertAlmostEqual(line.factor_base_uom_qty, 150.0, places=2)
        self.assertEqual(line.factor_base_uom_display, "= 150.00 lb")

    def test_same_category_no_display(self):
        """Line UoM in the same category as base UoM → qty=0.0."""
        line = self._make_po_line(10.0, self.uom_lb)
        self.assertEqual(line.factor_base_uom_qty, 0.0)
        self.assertEqual(line.factor_base_uom_display, "")

    def test_missing_factor_no_display(self):
        """Same-tree UoM with no factor row → qty=0.0, no exception.

        kg and lb share the mass tree (common reference), so the scoping
        constraint allows the line and the display compute stays empty because
        the line UoM is not a factor delegate.
        """
        product2 = self.env["product.product"].create(
            {
                "name": "No Factor Product PO",
                "uom_id": self.uom_lb.id,
                "standard_price": 3.0,
            }
        )
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "date_order": date.today(),
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product2.id,
                            "product_qty": 2.0,
                            "product_uom_id": self.uom_kg.id,
                            "price_unit": 3.0,
                            "date_planned": date.today(),
                            "name": product2.name,
                        },
                    )
                ],
            }
        )
        line = po.order_line
        self.assertEqual(line.factor_base_uom_qty, 0.0)
        self.assertEqual(line.factor_base_uom_display, "")
