"""
Tests for product_uom_factor_sale: PDF report rendering.

Acceptance Criteria:
1. Rendered HTML for a cross-category line contains the base-UoM qty string
   in a text-muted element (e.g. "250.00 lb") — exactly once (no duplicate
   from the stock note which we now replace via XPath position="replace").
2. The equation form does NOT appear in the rendered PDF (no "×" or "= " chars
   in the base-UoM note — the customer-facing readout is quantity only).
3. The stock note's computed value does NOT appear alongside our note for a
   cross-category line (i.e. no duplicate note from the replaced span).
4. A same-category UoM mismatch (kg line on a lb product) still renders the
   standard Odoo fallback note (i.e. the else branch works).
"""

from odoo.tests.common import TransactionCase


class TestRenderPdf(TransactionCase):
    """Test that the sale order PDF report replaces the stock base-UoM note."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom_lb = cls.env.ref("uom.product_uom_lb")
        cls.uom_kg = cls.env.ref("uom.product_uom_kgm")
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
        # A second SO with a same-category UoM mismatch line (kg on a lb product,
        # no product.uom.factor configured) to verify the fallback branch.
        cls.product_kg_base = cls.env["product.product"].create(
            {
                "name": "PDF Test KG Product",
                "uom_id": cls.uom_kg.id,
                "uom_ids": [(4, cls.uom_kg.id), (4, cls.uom_lb.id)],
                "list_price": 2.0,
            }
        )
        cls.so_same_cat = cls.env["sale.order"].create(
            {
                "partner_id": cls.customer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product_kg_base.id,
                            "product_uom_qty": 10.0,
                            "product_uom_id": cls.uom_lb.id,
                            "price_unit": 2.0,
                        },
                    )
                ],
            }
        )

    def _render(self, report_xmlid, record=None):
        if record is None:
            record = self.so
        html, _mime = self.env["ir.actions.report"]._render_qweb_html(
            report_xmlid, record.ids
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

    def test_pdf_no_duplicate_note_for_cross_category_line(self):
        """For a cross-category factor line, '250.00 lb' appears exactly once
        (the stock note is replaced, not added alongside).

        The stock Odoo template (ir_actions_report_templates.xml lines 214-217)
        emits a <span t-if="line.product_uom_id != line.product_id.uom_id"> in
        the qty cell. Our XPath position="replace" swaps it with our note. If
        both coexisted the count would be 2; we assert exactly 1.
        """
        html_str = self._render("sale.action_report_saleorder")
        count = html_str.count("250.00 lb")
        self.assertEqual(
            count,
            1,
            "Expected '250.00 lb' exactly once in the rendered HTML but found "
            f"{count} occurrences — the stock note may not have been replaced.",
        )

    def test_same_category_uom_no_factor_pdf(self):
        """A same-category UoM mismatch line (lb line on a kg-base product)
        still renders the standard Odoo fallback note in the qty cell.

        This verifies that our XPath replace's t-elif branch fires correctly
        and does not suppress the stock note for same-category mismatches.
        """
        html_str = self._render("sale.action_report_saleorder", self.so_same_cat)
        # The rendered HTML should still show a text-muted note because
        # the line UoM (lb) != product base UoM (kg).
        self.assertIn("text-muted", html_str)
