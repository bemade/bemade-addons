"""
Test bemade_packaging_qty_entry — Purchase Order side.

Acceptance Criteria (tests 1–6 from the design):
1. PO forward→package display: setting product_qty and packaging shows correct
   product_packaging_qty (ceil).
2. PO package→base inverse (PRIMARY): editing product_packaging_qty drives
   product_qty and product_uom_qty.
3. PO non-integer / single drum: package qty of 1 gives 205; of 3 gives 615.
4. PO stability / no loop: after inverse write, re-saving does not drift.
5. PO direct base edit preserves non-multiple: ceil shown, base NOT overwritten.
6. PO no packaging selected: no-op guard; normal base edit works.
"""

from odoo.tests import Form
from odoo.tests.common import TransactionCase


class TestPOPackageEntry(TransactionCase):
    """Purchase order package-qty-entry tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.uom_litre = cls.env.ref("uom.product_uom_litre")

        cls.vendor = cls.env["res.partner"].create(
            {"name": "Drum Vendor", "supplier_rank": 1}
        )

        cls.product = cls.env["product.product"].create(
            {
                "name": "Liquid Pigment",
                "uom_id": cls.uom_litre.id,
            }
        )
        cls.tmpl = cls.product.product_tmpl_id

        cls.pkg_type = cls.env["stock.package.type"].create(
            {"name": "205L Drum", "max_weight": 300}
        )

        # 205 L per drum, vendor-specific packaging
        cls.packaging = cls.env["product.uom.packaging"].create(
            {
                "name": "205L Drum",
                "product_tmpl_id": cls.tmpl.id,
                "uom_id": cls.uom_litre.id,
                "qty": 205.0,
                "package_type_id": cls.pkg_type.id,
                "partner_id": cls.vendor.id,
            }
        )

    # ------------------------------------------------------------------ helpers

    def _make_po_line_orm(self, qty, packaging=None):
        """Create a PO line via ORM (not Form), returns the line record."""
        po = self.env["purchase.order"].create({"partner_id": self.vendor.id})
        vals = {
            "order_id": po.id,
            "product_id": self.product.id,
            "product_qty": qty,
            "product_uom_id": self.uom_litre.id,
            "price_unit": 1.0,
            "name": self.product.name,
        }
        if packaging:
            vals["product_packaging_id"] = packaging.id
        return self.env["purchase.order.line"].create(vals)

    # ------------------------------------------------------------------ test 1

    def test_01_forward_compute_displays_package_count(self):
        """Forward compute: product_qty=410 + 205L packaging → 2 packages (ceil)."""
        line = self._make_po_line_orm(410.0, self.packaging)
        self.assertAlmostEqual(line.product_packaging_qty, 2.0)

    # ------------------------------------------------------------------ test 2

    def test_02_inverse_sets_base_qty_from_package_qty(self):
        """PRIMARY: editing product_packaging_qty=2 sets product_qty=410."""
        po = self.env["purchase.order"].create({"partner_id": self.vendor.id})
        with Form(po) as po_form:
            with po_form.order_line.new() as line:
                line.product_id = self.product
                line.product_packaging_id = self.packaging
                line.product_packaging_qty = 2.0
                self.assertAlmostEqual(line.product_qty, 410.0, places=2)

    # ------------------------------------------------------------------ test 3

    def test_03_single_and_three_drums(self):
        """1 drum → 205, 3 drums → 615."""
        po = self.env["purchase.order"].create({"partner_id": self.vendor.id})
        with Form(po) as po_form:
            with po_form.order_line.new() as line:
                line.product_id = self.product
                line.product_packaging_id = self.packaging
                line.product_packaging_qty = 1.0
                self.assertAlmostEqual(line.product_qty, 205.0, places=2)

        po2 = self.env["purchase.order"].create({"partner_id": self.vendor.id})
        with Form(po2) as po_form:
            with po_form.order_line.new() as line:
                line.product_id = self.product
                line.product_packaging_id = self.packaging
                line.product_packaging_qty = 3.0
                self.assertAlmostEqual(line.product_qty, 615.0, places=2)

    # ------------------------------------------------------------------ test 4

    def test_04_stability_no_loop_on_resave(self):
        """After inverse write, re-saving must not drift values."""
        line = self._make_po_line_orm(0.0, self.packaging)
        line.write({"product_packaging_qty": 2.0})
        self.assertAlmostEqual(line.product_qty, 410.0, places=2)
        self.assertAlmostEqual(line.product_packaging_qty, 2.0, places=2)

        # Re-save (another write without changing anything)
        line.write({"product_packaging_qty": 2.0})
        self.assertAlmostEqual(line.product_qty, 410.0, places=2)
        self.assertAlmostEqual(line.product_packaging_qty, 2.0, places=2)

    # ------------------------------------------------------------------ test 5

    def test_05_direct_base_edit_preserves_non_multiple(self):
        """Direct product_qty=300 with 205L packaging → ceil=2 packages shown,
        BUT product_qty stays 300 (inverse does NOT fire on base edits)."""
        line = self._make_po_line_orm(300.0, self.packaging)
        # Forward compute should show ceil(300/205) = 2
        self.assertAlmostEqual(line.product_packaging_qty, 2.0)
        # Base qty must remain 300 — inverse must not have overwritten it
        self.assertAlmostEqual(line.product_qty, 300.0, places=2)

    # ------------------------------------------------------------------ test 6

    def test_06_no_packaging_guard(self):
        """With no packaging selected, product_packaging_qty stays 0 and editing
        product_qty works normally."""
        line = self._make_po_line_orm(100.0, packaging=None)
        self.assertAlmostEqual(line.product_packaging_qty, 0.0)
        # Setting package qty with no packaging is a no-op (guard)
        line.write({"product_packaging_qty": 5.0})
        # product_qty should not have changed because guard fired
        self.assertAlmostEqual(line.product_qty, 100.0, places=2)

    # ------------------------------------------------------------------ test 9 (view smoke — PO)

    def test_09_view_smoke_po_form_loads(self):
        """Instantiating a PO Form exercises the reordered view XML;
        product_packaging_qty must be non-readonly in the line."""
        po = self.env["purchase.order"].create({"partner_id": self.vendor.id})
        # This will raise if the view XML is broken
        with Form(po) as po_form:
            with po_form.order_line.new() as line:
                line.product_id = self.product
                line.product_packaging_id = self.packaging
                # If product_packaging_qty were readonly, the next line would raise
                line.product_packaging_qty = 1.0
                self.assertAlmostEqual(line.product_qty, 205.0, places=2)
