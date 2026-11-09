# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: an open request for quotation is Indicative evidence.

ACCEPTANCE CRITERIA
1. An open RFQ (draft or sent) with a unit price, and nothing else, resolves
   as Indicative and reads
   "Indicative. Quoted {price} on RFQ {name}, not yet confirmed."
2. An RFQ line priced at zero is not evidence.
3. With a Firm price on file, the Firm price wins; a newer RFQ is reported as
   a note, an older one is not.
4. An RFQ beats an Estimated price (aged or undated).
5. An RFQ waiting for approval or a cancelled one is not an open RFQ.
6. An open RFQ older than the price age window (6 months) is ignored.
"""
from odoo.tests import tagged

from .common import PurchaseCostSourceCommon


@tagged("-at_install", "post_install")
class TestRfq(PurchaseCostSourceCommon):
    def test_rfq_only_is_indicative(self):
        rfq = self._order(12.5, state="draft")
        resolution = self._resolve()
        self.assertEqual(resolution.confidence, "indicative")
        self.assertAlmostEqual(resolution.unit_cost, 12.5)
        self.assertEqual(
            resolution.evidence,
            [
                f"Indicative. Quoted {self._money(12.5)} on RFQ {rfq.name}, "
                "not yet confirmed."
            ],
        )

    def test_sent_rfq_counts(self):
        self._order(12.5, state="sent")
        self.assertEqual(self._resolve().confidence, "indicative")

    def test_zero_priced_rfq_is_not_evidence(self):
        self._order(0.0, state="draft")
        self.assertEqual(self._resolve().confidence, "unknown")

    def test_firm_price_wins_and_newer_rfq_is_noted(self):
        self._order(40.0, on=self._months_ago(2))
        rfq = self._order(12.5, state="draft", on=self._months_ago(0))
        resolution = self._resolve()
        self.assertEqual(resolution.confidence, "firm")
        self.assertAlmostEqual(resolution.unit_cost, 40.0)
        self.assertEqual(len(resolution.notes), 1)
        self.assertIn(rfq.name, resolution.notes[0])

    def test_older_rfq_beside_firm_is_not_noted(self):
        self._order(12.5, state="draft", on=self._months_ago(3))
        self._order(40.0, on=self._months_ago(1))
        resolution = self._resolve()
        self.assertEqual(resolution.confidence, "firm")
        self.assertEqual(resolution.notes, [])

    def test_rfq_beats_aged_purchase(self):
        self._order(40.0, on=self._months_ago(12))
        self._order(12.5, state="sent", on=self._months_ago(1))
        resolution = self._resolve()
        self.assertEqual(resolution.confidence, "indicative")
        self.assertAlmostEqual(resolution.unit_cost, 12.5)

    def test_rfq_beats_undated_supplier_price(self):
        self._supplier_price(55.0)
        self._order(12.5, state="draft")
        self.assertEqual(self._resolve().confidence, "indicative")

    def test_waiting_or_cancelled_rfq_is_not_open(self):
        self._order(12.5, state="to approve")
        self._order(13.5, state="cancel")
        self.assertEqual(self._resolve().confidence, "unknown")

    def test_rfq_older_than_age_window_is_ignored(self):
        self._order(12.5, state="draft", on=self._months_ago(7))
        self.assertEqual(self._resolve().confidence, "unknown")

    def test_rfq_inside_age_window_counts(self):
        self._order(12.5, state="sent", on=self._months_ago(5))
        self.assertEqual(self._resolve().confidence, "indicative")
