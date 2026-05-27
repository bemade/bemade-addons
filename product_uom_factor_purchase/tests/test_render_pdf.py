"""
Tests for product_uom_factor_purchase: PDF report rendering.

Acceptance Criteria:
1. Rendered HTML for a cross-category PO line contains the base-UoM qty string
   in a text-muted element (e.g. "150.00 lb").
2. Same for the quotation (RFQ) PDF report.
3. Equation form does not appear in either PDF.
"""

from datetime import date

from odoo.tests.common import TransactionCase


class TestRenderPdf(TransactionCase):
    """Test that purchase PDF reports inject the base-UoM note."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom_lb = cls.env.ref("uom.product_uom_lb")
        # "Bag" is a standalone root UoM (no relative_uom_id) so it has no
        # common reference with any weight/volume UoM — i.e. it is cross-category
        # relative to lb/kg in the Odoo 19 tree-based UoM model.
        cls.uom_bag = cls.env["uom.uom"].create(
            {
                "name": "BagPurchasePDF",
                "relative_factor": 1.0,
            }
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "PDF Test Vendor", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "PDF Test Powder PO",
                "uom_id": cls.uom_lb.id,
                "uom_ids": [(4, cls.uom_lb.id), (4, cls.uom_bag.id)],
                "standard_price": 3.0,
            }
        )
        cls.env["product.uom.factor"].create(
            {
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "uom_id": cls.uom_bag.id,
                "factor": 50.0,
            }
        )
        cls.po = cls.env["purchase.order"].create(
            {
                "partner_id": cls.vendor.id,
                "date_order": date.today(),
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product.id,
                            "product_qty": 3.0,
                            "product_uom_id": cls.uom_bag.id,
                            "price_unit": 3.0,
                            "date_planned": date.today(),
                            "name": cls.product.name,
                        },
                    )
                ],
            }
        )

    def _render(self, report_xmlid):
        html, _mime = self.env["ir.actions.report"]._render_qweb_html(
            report_xmlid, self.po.ids
        )
        return html.decode("utf-8") if isinstance(html, bytes) else html

    def test_purchase_order_pdf_contains_base_uom_qty(self):
        """PO confirmed PDF contains '150.00 lb' in a text-muted note."""
        html_str = self._render("purchase.action_report_purchase_order")
        self.assertIn("150.00 lb", html_str)
        self.assertIn("text-muted", html_str)

    def test_purchase_quotation_pdf_contains_base_uom_qty(self):
        """PO quotation/RFQ PDF contains '150.00 lb' in a text-muted note."""
        html_str = self._render("purchase.report_purchase_quotation")
        self.assertIn("150.00 lb", html_str)
        self.assertIn("text-muted", html_str)

    def test_no_equation_form_in_pdfs(self):
        """Neither PDF contains the equation form '× 150.00 lb'."""
        for xmlid in (
            "purchase.action_report_purchase_order",
            "purchase.report_purchase_quotation",
        ):
            html_str = self._render(xmlid)
            self.assertNotIn("× 150.00 lb", html_str)
            self.assertNotIn("150.00 lb ×", html_str)
