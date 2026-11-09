# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: a price a vendor quoted but nobody confirmed is "Indicative".

A quotation from a vendor is better than a guess and worse than a promise.
The engine gives it its own level so a plugin (purchase RFQs, for one) only
has to supply the evidence.

ACCEPTANCE CRITERIA
1. "indicative" is a confidence level, ranked between Firm and Estimated:
   firm > indicative > estimated > unknown.
2. An indicative source alone resolves as Indicative.
3. An indicative source does not beat Firm evidence (an agreement in force, or
   a dated price within the age window), whatever its date.
4. An indicative source beats Estimated evidence (an aged or undated price).
5. When Firm evidence wins and an indicative source is newer, the indicative
   one is reported as a note beside the result, not dropped.
6. A blend is as weak as its weakest part: stock plus an indicative
   remainder is Indicative.
"""
from unittest.mock import patch

from odoo.tests import tagged

from ..tools.cost_source import CONFIDENCE_ORDER, CostSource
from .common import ProductCostSourceCommon


@tagged("-at_install", "post_install")
class TestIndicative(ProductCostSourceCommon):
    def _quoted(self, price, priced_on):
        model = type(self.env["product.product"])
        base = model._cost_source_price_candidates

        def patched(record, qty, date, currency, company):
            candidates = base(record, qty, date, currency, company)
            candidates.append(
                CostSource(
                    key="quoted",
                    qty=qty,
                    unit_price=price,
                    priced_on=priced_on,
                    indicative=True,
                )
            )
            return candidates

        return patch.object(model, "_cost_source_price_candidates", patched)

    def test_level_order(self):
        self.assertEqual(
            CONFIDENCE_ORDER, ["unknown", "estimated", "indicative", "firm"]
        )

    def test_indicative_alone(self):
        with self._quoted(60.0, self._months_ago(0)):
            resolution = self._resolve()
        self.assertEqual(resolution.confidence, "indicative")
        self.assertAlmostEqual(resolution.unit_cost, 60.0)

    def test_firm_beats_newer_indicative_and_notes_it(self):
        self._supplier_price(75.0, date_start=self._months_ago(2))
        with self._quoted(60.0, self._months_ago(0)):
            resolution = self._resolve()
        self.assertEqual(resolution.confidence, "firm")
        self.assertAlmostEqual(resolution.unit_cost, 75.0)
        self.assertEqual(len(resolution.notes), 1)

    def test_older_indicative_beside_firm_is_not_noted(self):
        self._supplier_price(75.0, date_start=self._months_ago(1))
        with self._quoted(60.0, self._months_ago(3)):
            resolution = self._resolve()
        self.assertEqual(resolution.confidence, "firm")
        self.assertEqual(resolution.notes, [])

    def test_indicative_beats_estimated(self):
        self._supplier_price(75.0, date_start=self._months_ago(20))
        with self._quoted(60.0, self._months_ago(10)):
            resolution = self._resolve()
        self.assertEqual(resolution.confidence, "indicative")
        self.assertAlmostEqual(resolution.unit_cost, 60.0)

    def test_indicative_beats_undated(self):
        self._supplier_price(75.0)
        with self._quoted(60.0, self._months_ago(1)):
            self.assertEqual(self._resolve().confidence, "indicative")

    def test_blend_with_indicative_is_indicative(self):
        self._set_stock_value(10.0)
        with self._quoted(60.0, self._months_ago(0)):
            resolution = self._resolve(qty=10, qty_from_stock=4)
        self.assertEqual(resolution.confidence, "indicative")
