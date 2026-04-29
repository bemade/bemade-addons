"""
Test UC3: Packaging Dimensions Accessible from SO Line

Acceptance Criteria:
1. For a SO line with packaging set, the packaging's package_type_id dimensions
   (packaging_length, width, height, base_weight) are reachable via the line's
   packaging relationship — confirms shipping team can access them.
2. Rendering the SO form via Form() with a packaged line doesn't raise an error
   (view fields are properly declared).
"""

from odoo.tests import Form
from odoo.tests.common import TransactionCase


class TestUCPackagingDimensionsVisible(TransactionCase):
    """Test UC3: packaging dimensions reachable from SO line."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.customer = cls.env["res.partner"].create(
            {"name": "Dimensions Test Customer", "customer_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Box Product",
                "uom_id": cls.uom_unit.id,
                "list_price": 5.0,
            }
        )
        cls.tmpl = cls.product.product_tmpl_id

        cls.pkg_type = cls.env["stock.package.type"].create(
            {
                "name": "Export Box",
                "packaging_length": 60,
                "width": 40,
                "height": 30,
                "base_weight": 1.5,
                "max_weight": 20,
            }
        )
        cls.packaging = cls.env["product.uom.packaging"].create(
            {
                "name": "Export Box",
                "product_tmpl_id": cls.tmpl.id,
                "uom_id": cls.uom_unit.id,
                "qty": 24.0,
                "package_type_id": cls.pkg_type.id,
            }
        )

    def test_dimensions_reachable_via_line(self):
        """Packaging dimensions are accessible through line.product_packaging_id."""
        so = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 48.0,
                            "product_uom_id": self.uom_unit.id,
                            "price_unit": 5.0,
                            "product_packaging_id": self.packaging.id,
                        },
                    )
                ],
            }
        )
        line = so.order_line
        self.assertEqual(
            line.product_packaging_id.package_type_id.packaging_length, 60
        )
        self.assertEqual(line.product_packaging_id.package_type_id.width, 40)
        self.assertEqual(line.product_packaging_id.package_type_id.height, 30)
        self.assertEqual(
            line.product_packaging_id.package_type_id.base_weight, 1.5
        )

    def test_so_form_renders_with_packaging(self):
        """SO form renders without error when a line has packaging set."""
        so = self.env["sale.order"].create({"partner_id": self.customer.id})
        with Form(so) as so_form:
            with so_form.order_line.new() as line:
                line.product_id = self.product
                line.product_uom_qty = 24.0
                line.product_packaging_id = self.packaging
            self.assertEqual(len(so_form.order_line), 1)
        # Packaging should be saved
        self.assertEqual(so.order_line.product_packaging_id, self.packaging)
        self.assertEqual(so.order_line.product_packaging_qty, 1.0)
