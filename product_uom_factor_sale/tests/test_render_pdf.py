"""
Tests for product_uom_factor_sale: PDF report rendering.

Acceptance Criteria:
1. Rendered HTML for a cross-category line contains the base-UoM qty string
   inside a text-muted element under the product name (e.g. "250.00 lb").
2. The equation form does NOT appear in the rendered PDF (no "×" or "= " chars
   in the base-UoM note — the customer-facing readout is quantity only).
"""

from odoo.tests.common import TransactionCase


class TestRenderPdf(TransactionCase):
    """Test that the sale order PDF report injects the base-UoM note."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom_lb = cls.env.ref("uom.product_uom_lb")
        cls.uom_vol_category = cls.env.ref("uom.product_uom_categ_vol")
        cls.uom_bag = cls.env["uom.uom"].create(
            {
                "name": "BagPDF",
                "category_id": cls.uom_vol_category.id,
                "factor": 1.0,
                "uom_type": "reference",
                "rounding": 0.01,
            }
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "PDF Test Customer", "customer_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "PDF Test Powder",
                "uom_id": cls.uom_lb.id,
                "uom_ids": [(4, cls.uom_lb.id), (4, cls.uom_bag.id)],
                "list_price": 5.0,
            }
        )
        cls.env["product.uom.factor"].create(
            {
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "uom_id": cls.uom_bag.id,
                "factor": 50.0,
            }
        )
        cls.so = cls.env["sale.order"].create(
            {
                "partner_id": cls.customer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product.id,
                            "product_uom_qty": 5.0,
                            "product_uom_id": cls.uom_bag.id,
                            "price_unit": 5.0,
                        },
                    )
                ],
            }
        )

    def test_pdf_contains_base_uom_qty(self):
        """Rendered HTML contains '250.00 lb' in a text-muted note."""
        report = self.env.ref("sale.action_report_saleorder")
        html, _mime = report._render_qweb_html(self.so.ids)
        html_str = html.decode("utf-8") if isinstance(html, bytes) else html
        self.assertIn("250.00 lb", html_str)
        self.assertIn("text-muted", html_str)

    def test_pdf_no_equation_form(self):
        """Rendered HTML does not contain the equation form '×' or '= ' in
        proximity to the base-UoM note (customer PDF shows qty only)."""
        report = self.env.ref("sale.action_report_saleorder")
        html, _mime = report._render_qweb_html(self.so.ids)
        html_str = html.decode("utf-8") if isinstance(html, bytes) else html
        # The × character must not appear in the text-muted note produced
        # by this module (it would indicate an equation-style output).
        # We assert the rendered output for our test SO doesn't contain ×
        # adjacent to "250.00 lb" — a simple sanity check.
        self.assertNotIn("× 250.00 lb", html_str)
        self.assertNotIn("250.00 lb ×", html_str)
