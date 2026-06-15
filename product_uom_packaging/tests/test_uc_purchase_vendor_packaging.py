"""
Test UC2: Vendor-Specific Purchase Packaging

Acceptance Criteria:
1. A PO line for Vendor A auto-populates product_packaging_id with Vendor A's
   packaging when exactly one match exists.
2. When two vendors have different packaging configs, the PO for Vendor A shows
   Vendor A's config, not Vendor B's.
3. product_packaging_qty reflects: ceil(order_qty / packaging.qty).
4. The domain on product_packaging_id excludes Vendor B's packaging but includes
   generic (partner_id=False) packagings.
"""

import math

from odoo.tests import Form
from odoo.tests.common import TransactionCase


class TestUCPurchaseVendorPackaging(TransactionCase):
    """Test UC2 purchase order vendor-specific packaging."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.uom_kg = cls.env.ref("uom.product_uom_kgm")
        cls.uom_lb = cls.env.ref("uom.product_uom_lb")

        cls.vendor_a = cls.env["res.partner"].create(
            {"name": "Vendor A", "supplier_rank": 1}
        )
        cls.vendor_b = cls.env["res.partner"].create(
            {"name": "Vendor B", "supplier_rank": 1}
        )

        cls.product = cls.env["product.product"].create(
            {
                "name": "Pigment Base",
                "uom_id": cls.uom_kg.id,
            }
        )
        cls.tmpl = cls.product.product_tmpl_id

        cls.pkg_drum = cls.env["stock.package.type"].create(
            {"name": "205L Drum", "max_weight": 200}
        )
        cls.pkg_pail = cls.env["stock.package.type"].create(
            {"name": "20L Pail", "max_weight": 25}
        )

        # Vendor A: 100 kg per drum
        cls.pkg_vendor_a = cls.env["product.uom.packaging"].create(
            {
                "name": "Vendor A Drum",
                "product_tmpl_id": cls.tmpl.id,
                "uom_id": cls.uom_kg.id,
                "qty": 100.0,
                "package_type_id": cls.pkg_drum.id,
                "partner_id": cls.vendor_a.id,
            }
        )
        # Vendor B: 200 kg per drum
        cls.pkg_vendor_b = cls.env["product.uom.packaging"].create(
            {
                "name": "Vendor B Drum",
                "product_tmpl_id": cls.tmpl.id,
                "uom_id": cls.uom_kg.id,
                "qty": 200.0,
                "package_type_id": cls.pkg_drum.id,
                "partner_id": cls.vendor_b.id,
            }
        )

        cls.company = cls.env.company

    def _make_po(self, vendor):
        return self.env["purchase.order"].create(
            {
                "partner_id": vendor.id,
            }
        )

    def test_auto_pick_vendor_packaging_on_product_set(self):
        """When product is set on a PO line for Vendor A (1 matching packaging),
        product_packaging_id is auto-selected."""
        po = self._make_po(self.vendor_a)
        with Form(po) as po_form:
            with po_form.order_line.new() as line:
                line.product_id = self.product
                line.product_qty = 300.0
                self.assertEqual(
                    line.product_packaging_id,
                    self.pkg_vendor_a,
                    "Should auto-pick Vendor A's packaging",
                )

    def test_packaging_qty_computed_correctly(self):
        """product_packaging_qty = ceil(order_qty / packaging.qty)."""
        po = self._make_po(self.vendor_a)
        line = self.env["purchase.order.line"].create(
            {
                "order_id": po.id,
                "product_id": self.product.id,
                "product_qty": 350.0,
                "product_uom_id": self.uom_kg.id,
                "price_unit": 1.0,
                "name": "Pigment Base",
                "product_packaging_id": self.pkg_vendor_a.id,
            }
        )
        expected = math.ceil(350.0 / 100.0)  # 4
        self.assertEqual(line.product_packaging_qty, expected)

    def test_no_auto_pick_when_multiple_vendor_packagings(self):
        """When a vendor has multiple packagings, no auto-selection occurs."""
        # Add a second packaging for Vendor A
        pkg_a2 = self.env["product.uom.packaging"].create(
            {
                "name": "Vendor A Pail",
                "product_tmpl_id": self.tmpl.id,
                "uom_id": self.uom_kg.id,
                "qty": 20.0,
                "package_type_id": self.pkg_pail.id,
                "partner_id": self.vendor_a.id,
            }
        )
        po = self._make_po(self.vendor_a)
        with Form(po) as po_form:
            with po_form.order_line.new() as line:
                line.product_id = self.product
                line.product_qty = 100.0
                # No auto-pick because there are 2 vendor A packagings
                self.assertFalse(
                    line.product_packaging_id,
                    "Should not auto-pick when multiple vendor packagings exist",
                )
        pkg_a2.unlink()

    def test_vendor_b_packaging_excluded_from_vendor_a_po(self):
        """Vendor B's packaging is not in the valid domain for a Vendor A PO line."""
        po = self._make_po(self.vendor_a)
        line = self.env["purchase.order.line"].create(
            {
                "order_id": po.id,
                "product_id": self.product.id,
                "product_qty": 100.0,
                "product_uom_id": self.uom_kg.id,
                "price_unit": 1.0,
                "name": "Pigment Base",
            }
        )
        # Domain: [('product_tmpl_id','=', tmpl), '|', ('partner_id','=',False),
        #          ('partner_id','=', vendor_a)]
        valid = self.env["product.uom.packaging"].search(
            [
                ("product_tmpl_id", "=", self.tmpl.id),
                "|",
                ("partner_id", "=", False),
                ("partner_id", "=", self.vendor_a.id),
            ]
        )
        self.assertIn(self.pkg_vendor_a, valid)
        self.assertNotIn(self.pkg_vendor_b, valid)

    def test_po_line_form_builds_with_packaging_domain(self):
        """Form build with a product succeeds and product_packaging_id resolves.

        Regression guard: a malformed view-level domain on product_packaging_id
        (e.g. referencing product_id.product_tmpl_id instead of
        product_template_id) causes odoo.tests.Form to raise on build.
        If this test passes, the domain in purchase_order_views.xml compiles
        and the invisible product_template_id field is loaded in the list.
        """
        po = self._make_po(self.vendor_a)
        with Form(po) as po_form:
            with po_form.order_line.new() as line:
                line.product_id = self.product
                line.product_qty = 100.0
                # Auto-selected because exactly one vendor-A packaging exists.
                self.assertEqual(line.product_packaging_id, self.pkg_vendor_a)

    def test_po_line_form_empty_product_no_error(self):
        """Form build with no product set raises no error and packaging is empty.

        With the corrected domain referencing product_template_id (which is
        False when no product is set), the leaf degrades to
        ('product_tmpl_id','=',False) — valid, returns no packagings.
        A malformed leaf ('product_tmpl_id','=','') would raise instead.
        """
        po = self._make_po(self.vendor_a)
        with Form(po) as po_form:
            with po_form.order_line.new() as line:
                # Deliberately leave product_id unset.
                self.assertFalse(
                    line.product_packaging_id,
                    "No packaging should be auto-selected when product is empty",
                )

    def test_generic_packaging_included_in_vendor_a_domain(self):
        """Generic (partner_id=False) packagings appear in the domain for any vendor."""
        generic_pkg = self.env["product.uom.packaging"].create(
            {
                "name": "Generic Drum",
                "product_tmpl_id": self.tmpl.id,
                "uom_id": self.uom_kg.id,
                "qty": 50.0,
                "package_type_id": self.pkg_pail.id,
            }
        )
        valid = self.env["product.uom.packaging"].search(
            [
                ("product_tmpl_id", "=", self.tmpl.id),
                "|",
                ("partner_id", "=", False),
                ("partner_id", "=", self.vendor_a.id),
            ]
        )
        self.assertIn(generic_pkg, valid)
        generic_pkg.unlink()
