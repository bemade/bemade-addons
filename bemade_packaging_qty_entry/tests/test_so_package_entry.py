"""
Test bemade_packaging_qty_entry — Sale Order side.

Acceptance Criteria (tests 7–9 from the design):
7. SO package→base inverse: editing product_packaging_qty drives product_uom_qty.
8. SO forward display + confirm: direct product_uom_qty edit shows correct ceil;
   confirming SO raises no UoM-mismatch error.
9. View smoke (SO): Form loads the reordered view; product_packaging_qty editable.
"""

from odoo.tests import Form
from odoo.tests.common import TransactionCase


class TestSOPackageEntry(TransactionCase):
    """Sale order package-qty-entry tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.uom_unit = cls.env.ref("uom.product_uom_unit")

        cls.customer = cls.env["res.partner"].create(
            {"name": "Test Customer", "customer_rank": 1}
        )

        cls.product = cls.env["product.product"].create(
            {
                "name": "Widget",
                "uom_id": cls.uom_unit.id,
                "list_price": 10.0,
                "type": "consu",
            }
        )
        cls.tmpl = cls.product.product_tmpl_id

        cls.pkg_type = cls.env["stock.package.type"].create(
            {"name": "12-Unit Box"}
        )

        # Generic packaging: 12 units per box (no partner_id → SO-compatible)
        cls.packaging = cls.env["product.uom.packaging"].create(
            {
                "name": "12-Unit Box",
                "product_tmpl_id": cls.tmpl.id,
                "uom_id": cls.uom_unit.id,
                "qty": 12.0,
                "package_type_id": cls.pkg_type.id,
            }
        )

    # ------------------------------------------------------------------ helpers

    def _make_so_line_orm(self, qty, packaging=None):
        """Create a SO line via ORM, returns the line record."""
        so_vals = {
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
                        "name": self.product.name,
                        **(
                            {"product_packaging_id": packaging.id}
                            if packaging
                            else {}
                        ),
                    },
                )
            ],
        }
        so = self.env["sale.order"].create(so_vals)
        return so.order_line

    # ------------------------------------------------------------------ test 7

    def test_07_so_inverse_sets_base_qty_from_package_qty(self):
        """PRIMARY (SO): editing product_packaging_qty=2 sets product_uom_qty=24."""
        so = self.env["sale.order"].create({"partner_id": self.customer.id})
        with Form(so) as so_form:
            with so_form.order_line.new() as line:
                line.product_id = self.product
                line.product_packaging_id = self.packaging
                line.product_packaging_qty = 2.0
                self.assertAlmostEqual(line.product_uom_qty, 24.0, places=2)

    # ------------------------------------------------------------------ test 8

    def test_08_so_forward_display_and_confirm(self):
        """Direct product_uom_qty=36 shows 3 packages (ceil(36/12));
        confirming the SO raises no error."""
        line = self._make_so_line_orm(36.0, self.packaging)
        self.assertAlmostEqual(line.product_packaging_qty, 3.0)
        # Confirm the SO — must not raise
        line.order_id.action_confirm()
        self.assertEqual(line.order_id.state, "sale")

    # ------------------------------------------------------------------ test 9 (view smoke — SO)

    def test_09_view_smoke_so_form_loads(self):
        """Instantiating a SO Form exercises the reordered view XML;
        product_packaging_qty must be non-readonly in the line."""
        so = self.env["sale.order"].create({"partner_id": self.customer.id})
        with Form(so) as so_form:
            with so_form.order_line.new() as line:
                line.product_id = self.product
                line.product_packaging_id = self.packaging
                # If product_packaging_qty were readonly, the next line would raise
                line.product_packaging_qty = 2.0
                self.assertAlmostEqual(line.product_uom_qty, 24.0, places=2)
