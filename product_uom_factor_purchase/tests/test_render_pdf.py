"""
Tests for product_uom_factor_purchase: PDF report rendering.

Acceptance Criteria:
1. Rendered HTML for a cross-category PO line contains the base-UoM qty string
   in a text-muted element (e.g. "150.00 lb") — exactly once (no duplicate
   from the stock note which we now replace via XPath position="replace").
2. Same for the quotation (RFQ) PDF report.
3. Equation form does not appear in either PDF.
4. The stock note's computed value does NOT appear alongside our note for a
   cross-category line (i.e. no duplicate note from the replaced span).
5. A same-category UoM mismatch (lb line on a kg-base product) still renders
   the standard Odoo fallback note (i.e. the else branch works).
"""

from datetime import date

from odoo.tests.common import TransactionCase


class TestRenderPdf(TransactionCase):
    """Test that purchase PDF reports replace the stock base-UoM note."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom_lb = cls.env.ref("uom.product_uom_lb")
        cls.uom_kg = cls.env.ref("uom.product_uom_kgm")
        # "BagPurchasePDF" is a standalone root UoM (no relative_uom_id) so it
        # has no common reference with any weight/volume UoM — cross-category.
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
        # A second PO with a same-category UoM mismatch line (lb on a kg-base
        # product, no product.uom.factor) to test the fallback branch.
        cls.product_kg_base = cls.env["product.product"].create(
            {
                "name": "PDF Test KG Product PO",
                "uom_id": cls.uom_kg.id,
                "uom_ids": [(4, cls.uom_kg.id), (4, cls.uom_lb.id)],
                "standard_price": 1.0,
            }
        )
        cls.po_same_cat = cls.env["purchase.order"].create(
            {
                "partner_id": cls.vendor.id,
                "date_order": date.today(),
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product_kg_base.id,
                            "product_qty": 10.0,
                            "product_uom_id": cls.uom_lb.id,
                            "price_unit": 1.0,
                            "date_planned": date.today(),
                            "name": cls.product_kg_base.name,
                        },
                    )
                ],
            }
        )

    def _render(self, report_xmlid, record=None):
        if record is None:
            record = self.po
        html, _mime = self.env["ir.actions.report"]._render_qweb_html(
            report_xmlid, record.ids
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

    def test_no_duplicate_note_for_cross_category_po(self):
        """For a cross-category factor line in confirmed PO, '150.00 lb' appears
        exactly once (the stock note is replaced, not added alongside)."""
        html_str = self._render("purchase.action_report_purchase_order")
        count = html_str.count("150.00 lb")
        self.assertEqual(
            count,
            1,
            "Expected '150.00 lb' exactly once in the PO PDF but found "
            f"{count} occurrences — the stock note may not have been replaced.",
        )

    def test_no_duplicate_note_for_cross_category_rfq(self):
        """For a cross-category factor line in RFQ, '150.00 lb' appears
        exactly once (the stock note is replaced, not added alongside)."""
        html_str = self._render("purchase.report_purchase_quotation")
        count = html_str.count("150.00 lb")
        self.assertEqual(
            count,
            1,
            "Expected '150.00 lb' exactly once in the RFQ PDF but found "
            f"{count} occurrences — the stock note may not have been replaced.",
        )

    def test_same_category_uom_no_factor_po_pdf(self):
        """A same-category UoM mismatch line (lb line on a kg-base product)
        still renders the standard Odoo fallback note in the confirmed PO PDF."""
        html_str = self._render(
            "purchase.action_report_purchase_order", self.po_same_cat
        )
        self.assertIn("text-muted", html_str)

    def test_same_category_uom_no_factor_rfq_pdf(self):
        """A same-category UoM mismatch line (lb line on a kg-base product)
        still renders the standard Odoo fallback note in the RFQ PDF."""
        html_str = self._render(
            "purchase.report_purchase_quotation", self.po_same_cat
        )
        self.assertIn("text-muted", html_str)
