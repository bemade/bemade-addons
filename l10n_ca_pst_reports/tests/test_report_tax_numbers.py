import re

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestReportTaxNumbers(TransactionCase):
    """Verify the company's GST/HST and PST numbers render exactly once
    in account.report_invoice on every external layout.

    On 19.0 the work is split between two upstream pieces:

    - web.external_layout_* renders ``<country.vat_label>: <vat>`` inside
      the company_address_list ul. For Canada that resolves to
      "GST/HST number: <vat>".
    - l10n_ca.pst_external_layout (called from each l10n_ca_external_layout_*)
      adds a "PST: <l10n_ca_pst>" <li> to the same list.

    This module used to override l10n_ca.pst_external_layout on 18.0 to
    re-render the GST line in a shorter "GST/HST:" form; on 19.0 that
    override emitted a second GST/HST line right next to the upstream
    one. The override has been removed and these tests pin that result.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({
            "name": "Test Canadian Company",
            "country_id": cls.env.ref("base.ca").id,
            "vat": "123456789",
            "l10n_ca_pst": "PST12345",
        })
        # Loading the chart of accounts also sets account_fiscal_country_id
        # which is what the templates' t-if conditions check.
        cls.env["account.chart.template"].try_loading("ca_2023", company=cls.company)

        cls.partner = cls.env["res.partner"].create({
            "name": "Test Customer",
            "country_id": cls.env.ref("base.ca").id,
        })
        cls.invoice = cls.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": cls.partner.id,
            "company_id": cls.company.id,
        })

    def _render_invoice_html(self):
        """Render account.report_invoice for self.invoice and return the
        resulting HTML as a plain string."""
        html, _kind = self.env["ir.actions.report"]._render_qweb_html(
            "account.report_invoice", [self.invoice.id]
        )
        return html.decode("utf-8") if isinstance(html, bytes) else str(html)

    @staticmethod
    def _count_gst_hst_short_form(html):
        """Count occurrences of the bare 18-style "GST/HST: <vat>" label.
        Uses a negative lookahead so we don't match the upstream Canadian
        vat_label "GST/HST number:" — only the bare 'GST/HST:'."""
        return len(re.findall(r"GST/HST(?!\s*number):", html))

    def test_invoice_renders_each_tax_number_once(self):
        """GST and PST should each appear exactly once in the company
        address list of the rendered invoice."""
        html = self._render_invoice_html()

        self.assertEqual(
            html.count("GST/HST number:"), 1,
            "Expected exactly one upstream-rendered GST/HST number line; "
            "duplicates indicate the 18-style override was reintroduced.",
        )
        self.assertIn("123456789", html)
        self.assertEqual(
            html.count("PST:"), 1,
            "Expected exactly one PST line (from l10n_ca.pst_external_layout); "
            "duplicates indicate this module is re-emitting it.",
        )
        self.assertIn("PST12345", html)
        self.assertEqual(
            self._count_gst_hst_short_form(html), 0,
            'Old 18-style "GST/HST:" label is back — that was the duplicate '
            "this module used to produce before the 19.0 fix.",
        )

    def test_no_duplicate_on_each_layout(self):
        """Same dedup invariant across every web.external_layout_* the
        report can be rendered with."""
        layouts = ["standard", "boxed", "bold", "striped", "bubble", "wave", "folder"]
        for layout in layouts:
            with self.subTest(layout=layout):
                self.company.external_report_layout_id = self.env.ref(
                    f"web.external_layout_{layout}"
                )
                html = self._render_invoice_html()
                self.assertEqual(
                    html.count("GST/HST number:"), 1,
                    f"GST/HST should appear once on {layout} layout",
                )
                self.assertEqual(
                    html.count("PST:"), 1,
                    f"PST should appear once on {layout} layout",
                )
                self.assertEqual(
                    self._count_gst_hst_short_form(html), 0,
                    f'18-style "GST/HST:" duplicate on {layout} layout',
                )
