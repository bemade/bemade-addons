# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: the quotation says, at a glance, how many lines are not firm.

ACCEPTANCE CRITERIA
1. The order's worst confidence is the weakest of its lines.
2. The summary counts the non-firm lines per level, worst first:
   "2 lines Unknown, 1 line Estimated".
3. An order whose lines are all firm has no summary (the badge is hidden).
4. In French it reads « 2 lignes Inconnu, 1 ligne Estimation ».
"""
from odoo.tests import tagged

from .common import SaleCostSourceCommon


@tagged("post_install", "-at_install")
class TestOrderSummary(SaleCostSourceCommon):
    def _mixed_order(self):
        estimated = self._storable("Estimated Part")
        self._seller(product=estimated, date_start=self._ago(9))
        firm = self._storable("Firm Part")
        self._seller(product=firm, date_end=self._ahead(months=3))
        unknown_a = self._storable("Unknown A")
        unknown_b = self._storable("Unknown B")
        return self._order(
            [
                {"product_id": firm.id},
                {"product_id": unknown_a.id},
                {"product_id": estimated.id},
                {"product_id": unknown_b.id},
            ]
        )

    def test_summary_counts_worst_first(self):
        order = self._mixed_order()
        self.assertEqual(order.cost_source_worst, "unknown")
        self.assertEqual(order.cost_source_summary, "2 lines Unknown, 1 line Estimated")

    def test_all_firm_has_no_summary(self):
        self._seller(date_end=self._ahead(months=3))
        order = self._order()
        self.assertEqual(order.cost_source_worst, "firm")
        self.assertFalse(order.cost_source_summary)

    def test_summary_in_french(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        self.env["ir.module.module"].search(
            [("name", "in", ("product_cost_source", "sale_cost_source"))]
        )._update_translations(["fr_FR"])
        order = self._mixed_order().with_context(lang="fr_FR")
        self.assertEqual(order.cost_source_summary, "2 lignes Inconnu, 1 ligne Estimation")
        self.assertEqual(
            order.order_line[1].cost_source_reason,
            "Inconnu. Aucun prix fournisseur et aucun historique d'achat.",
        )
