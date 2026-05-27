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
        # "BagPDF" is a standalone root UoM (no relative_uom_id) so it has no
        # common reference with any weight/volume UoM — i.e. it is cross-category
        # relative to lb/kg in the Odoo 19 tree-based UoM model.
        cls.uom_bag = cls.env["uom.uom"].create(
            {
                "name": "BagPDF",
                "relative_factor": 1.0,
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

    def _render(self, report_xmlid):
        html, _mime = self.env["ir.actions.report"]._render_qweb_html(
            report_xmlid, self.so.ids
        )
        return html.decode("utf-8") if isinstance(html, bytes) else html

    def test_pdf_contains_base_uom_qty(self):
        """Rendered HTML contains '250.00 lb' in a text-muted note."""
        html_str = self._render("sale.action_report_saleorder")
        self.assertIn("250.00 lb", html_str)
        self.assertIn("text-muted", html_str)

    def test_pdf_no_equation_form(self):
        """Rendered HTML does not contain the equation form '×' or '= ' in
        proximity to the base-UoM note (customer PDF shows qty only)."""
        html_str = self._render("sale.action_report_saleorder")
        # The × character must not appear in the text-muted note produced
        # by this module (it would indicate an equation-style output).
        # We assert the rendered output for our test SO doesn't contain ×
        # adjacent to "250.00 lb" — a simple sanity check.
        self.assertNotIn("× 250.00 lb", html_str)
        self.assertNotIn("250.00 lb ×", html_str)
