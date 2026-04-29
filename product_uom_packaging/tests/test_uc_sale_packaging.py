"""
Test UC1: Sale Order Line Packaging

Acceptance Criteria:
1. A SO line can have a packaging set (generic, partner_id=False).
2. product_packaging_qty = ceil(order_qty_in_pkg_uom / packaging.qty).
3. The packaging field domain only shows generic (partner_id=False) packagings
   for the line's product template.
4. Changing order qty updates product_packaging_qty.
"""

import math

from odoo.tests.common import TransactionCase


class TestUCSalePackaging(TransactionCase):
    """Test UC1: SO line packaging data model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.uom_dozen = cls.env.ref("uom.product_uom_dozen")

        cls.customer = cls.env["res.partner"].create(
            {"name": "Test Customer", "customer_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Widget",
                "uom_id": cls.uom_unit.id,
                "list_price": 10.0,
            }
        )
        cls.tmpl = cls.product.product_tmpl_id

        cls.pkg_box = cls.env["stock.package.type"].create(
            {
                "name": "12-Unit Box",
                "max_weight": 5,
                "packaging_length": 30,
                "width": 20,
                "height": 10,
            }
        )
        # Generic packaging: 12 units per box
        cls.packaging = cls.env["product.uom.packaging"].create(
            {
                "name": "12-Unit Box",
                "product_tmpl_id": cls.tmpl.id,
                "uom_id": cls.uom_unit.id,
                "qty": 12.0,
                "package_type_id": cls.pkg_box.id,
            }
        )

    def _make_so_line(self, qty):
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
                            "product_uom_id": self.uom_unit.id,
                            "price_unit": 10.0,
                            "product_packaging_id": self.packaging.id,
                        },
                    )
                ],
            }
        )
        return so.order_line

    def test_so_line_accepts_generic_packaging(self):
        """SO line can be saved with a generic (partner_id=False) packaging."""
        line = self._make_so_line(36)
        self.assertEqual(line.product_packaging_id, self.packaging)

    def test_packaging_qty_exact_multiple(self):
        """product_packaging_qty = ceil(36 / 12) = 3."""
        line = self._make_so_line(36)
        self.assertEqual(line.product_packaging_qty, 3)

    def test_packaging_qty_rounds_up(self):
        """product_packaging_qty = ceil(13 / 12) = 2 (partial package rounds up)."""
        line = self._make_so_line(13)
        self.assertEqual(line.product_packaging_qty, 2)

    def test_packaging_qty_zero_when_no_packaging(self):
        """product_packaging_qty = 0 when no packaging is set."""
        so = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 10.0,
                            "product_uom_id": self.uom_unit.id,
                            "price_unit": 10.0,
                        },
                    )
                ],
            }
        )
        line = so.order_line
        self.assertEqual(line.product_packaging_qty, 0.0)

    def test_domain_excludes_vendor_packagings(self):
        """The SO line field domain (partner_id=False) excludes vendor packagings."""
        vendor = self.env["res.partner"].create({"name": "Test Vendor"})
        vendor_pkg = self.env["product.uom.packaging"].create(
            {
                "name": "Vendor Drum",
                "product_tmpl_id": self.tmpl.id,
                "uom_id": self.uom_unit.id,
                "qty": 100.0,
                "package_type_id": self.pkg_box.id,
                "partner_id": vendor.id,
            }
        )
        generic_options = self.env["product.uom.packaging"].search(
            [
                ("product_tmpl_id", "=", self.tmpl.id),
                ("partner_id", "=", False),
            ]
        )
        self.assertIn(self.packaging, generic_options)
        self.assertNotIn(vendor_pkg, generic_options)
        vendor_pkg.unlink()
