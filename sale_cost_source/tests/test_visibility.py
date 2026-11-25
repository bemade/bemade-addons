# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: the indicator is for sales staff only, never for the customer.

ACCEPTANCE CRITERIA
1. The fields are restricted to the salesman group.
2. The order form shows the column, the line-form fields, the tooltip widget
   (cost_source_price, or its monetary twin cost_source_monetary) and the
   header badge to a salesperson.
3. A portal user cannot read the fields.
4. The printed quotation does not contain the indicator.
"""
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .common import SaleCostSourceCommon

FIELDS = ("cost_source_confidence", "cost_source_reason", "cost_source_explanation")


@tagged("post_install", "-at_install")
class TestVisibility(SaleCostSourceCommon):
    def test_fields_are_salesman_only(self):
        line_fields = self.env["sale.order.line"]._fields
        for name in FIELDS:
            self.assertEqual(line_fields[name].groups, "sales_team.group_sale_salesman")
        order_fields = self.env["sale.order"]._fields
        for name in ("cost_source_worst", "cost_source_summary"):
            self.assertEqual(order_fields[name].groups, "sales_team.group_sale_salesman")

    def test_form_shows_the_indicator_to_a_salesperson(self):
        user = new_test_user(self.env, login="cs_seller", groups="sales_team.group_sale_salesman")
        arch = self.env["sale.order"].with_user(user).get_view(view_type="form")["arch"]
        self.assertIn('name="cost_source_confidence"', arch)
        self.assertIn('name="cost_source_summary"', arch)
        # cost_source_price here; a module that wants the monetary display may
        # switch to cost_source_monetary, which carries the same tooltip.
        self.assertRegex(arch, r'name="price_unit"[^>]*widget="cost_source_(price|monetary)"')

    def test_portal_user_cannot_read(self):
        portal = new_test_user(self.env, login="cs_portal", groups="base.group_portal")
        line = self._line()
        with self.assertRaises(AccessError):
            line.with_user(portal).read(["cost_source_confidence"])

    def test_pdf_has_no_indicator(self):
        line = self._line()
        html, _fmt = self.env["ir.actions.report"]._render_qweb_html(
            "sale.action_report_saleorder", line.order_id.ids
        )
        html = html.decode()
        self.assertNotIn("Unknown. No vendor price", html)
        self.assertNotIn("cost_source", html)
