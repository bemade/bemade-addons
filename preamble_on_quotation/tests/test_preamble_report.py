from lxml import html

from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

MARKER = "PreambleMarkerForReportTest"


def _has_class(el, name):
    return name in (el.get("class") or "").split()


@tagged("post_install", "-at_install")
class TestPreambleOnReport(TransactionCase):
    """The PDF prints the preamble as a cover before the quotation.

    wkhtmltopdf renders every ``.article`` as its own document and gives it the
    header and footer at the same position, so a preamble article printed
    outside ``web.external_layout`` steals the quotation's header and footer:
    the quotation pages then print bare, without the company layout, and the
    page count restarts. The preamble must therefore go through the company's
    external layout itself, and must not force a page break of its own (the
    next article already starts on a new page; an extra break leaves a blank
    page whenever the preamble ends at a page boundary).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Report Preamble Customer"})
        cls.product = cls.env["product.product"].create(
            {"name": "Preamble Report Service", "type": "service"}
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "preamble": f"<p>{MARKER}</p>",
                "order_line": [Command.create({"product_id": cls.product.id})],
            }
        )

    def _render(self):
        content, _ = self.env["ir.actions.report"]._render_qweb_html(
            "sale.action_report_saleorder", self.order.ids
        )
        return html.fromstring(content)

    def _blocks(self, tree, name):
        return [d for d in tree.iter("div") if _has_class(d, name)]

    def test_each_article_has_its_own_header_and_footer(self):
        tree = self._render()
        articles = self._blocks(tree, "article")
        self.assertEqual(len(articles), 2, "expected the preamble and the quotation")
        self.assertEqual(len(self._blocks(tree, "header")), len(articles))
        self.assertEqual(len(self._blocks(tree, "footer")), len(articles))

    def test_preamble_is_the_first_article_and_carries_the_layout(self):
        preamble, quotation = self._blocks(self._render(), "article")[:2]
        self.assertIn(MARKER, preamble.text_content())
        self.assertNotIn(MARKER, quotation.text_content())
        company_class = f"o_company_{self.order.company_id.id}_layout"
        self.assertTrue(_has_class(preamble, company_class), "preamble printed outside the company layout")

    def test_preamble_does_not_force_a_page_break(self):
        preamble = self._blocks(self._render(), "article")[0]
        for el in preamble.iter():
            self.assertNotIn("page-break-after", el.get("style") or "")

    def test_no_preamble_article_without_preamble(self):
        self.order.preamble = False
        self.assertEqual(len(self._blocks(self._render(), "article")), 1)
