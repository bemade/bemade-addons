# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: every sentence starts with its verdict, in words a quoter uses.

A person scanning a quotation reads the first word and moves on. The verdict
comes first (Firm, Indicative, Estimated, Unknown, Warning), then the one fact
that justifies it.

ACCEPTANCE CRITERIA
1. A vendor price list in force with an end date reads
   "Firm. Vendor price list valid to {date}."
2. Partial stock coverage reads
   "Firm. {n} of {m} covered from stock at {price}; balance at vendor price."
   and full coverage "Firm. Covered from stock at {price}."
3. A last known price past the age window reads
   "Estimated. Last known price {date}, over {n} months old. No contract in
   force."
4. A dated last known price within the window reads
   "Firm. Last known price {date}, within the last {n} months."
5. An undated vendor price reads as an Estimated sentence that says its date
   is unknown.
6. Nothing known reads "Unknown. No vendor price and no purchase history."
7. A price expiring before delivery warns
   "Warning. Vendor price expires {date}, before this line's delivery date of
   {date}."
8. Stock covering part of the demand with no price for the rest names the
   uncovered quantity as Unknown, and the resolution is Unknown: a line that
   is partly unpriced is not firm, however firm its priced part is.
9. Dates are formatted in the user's language, not as ISO strings.
"""
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tools.misc import format_amount

from .common import ProductCostSourceCommon


@tagged("-at_install", "post_install")
class TestWording(ProductCostSourceCommon):
    def _money(self, amount):
        return format_amount(self.env, amount, self.company.currency_id)

    def test_price_list_in_force(self):
        end = fields.Date.today() + relativedelta(months=3)
        self._supplier_price(75.0, date_start=self._months_ago(1), date_end=end)
        self.assertEqual(
            self._resolve().evidence,
            [f"Firm. Vendor price list valid to {self._fmt(end)}."],
        )

    def test_partial_stock_coverage(self):
        self._set_stock_value(10.0)
        end = fields.Date.today() + relativedelta(months=3)
        self._supplier_price(15.0, date_end=end)
        evidence = self._resolve(qty=60, qty_from_stock=40).evidence
        self.assertEqual(
            evidence[0],
            f"Firm. 40 of 60 covered from stock at {self._money(10.0)}; "
            "balance at vendor price.",
        )
        self.assertTrue(evidence[1].startswith("Firm. Vendor price list valid to"))

    def test_full_stock_coverage(self):
        self._set_stock_value(10.0)
        self.assertEqual(
            self._resolve(qty=5, qty_from_stock=5).evidence,
            [f"Firm. Covered from stock at {self._money(10.0)}."],
        )

    def test_aged_last_known_price(self):
        agreed = self._months_ago(9)
        self._supplier_price(75.0, date_start=agreed)
        self.assertEqual(
            self._resolve().evidence,
            [
                f"Estimated. Last known price {self._fmt(agreed)}, over 6 months "
                "old. No contract in force."
            ],
        )

    def test_recent_last_known_price(self):
        agreed = self._months_ago(2)
        self._supplier_price(75.0, date_start=agreed)
        self.assertEqual(
            self._resolve().evidence,
            [f"Firm. Last known price {self._fmt(agreed)}, within the last 6 months."],
        )

    def test_undated_price(self):
        self._supplier_price(75.0)
        sentence = self._resolve().evidence[0]
        self.assertTrue(sentence.startswith("Estimated. "))
        self.assertIn("undated", sentence)

    def test_nothing_known(self):
        self.assertEqual(
            self._resolve().evidence,
            ["Unknown. No vendor price and no purchase history."],
        )

    def test_expiry_warning(self):
        end = fields.Date.today() + relativedelta(days=7)
        delivery = fields.Date.today() + relativedelta(months=2)
        self._supplier_price(75.0, date_start=self._months_ago(1), date_end=end)
        self.assertEqual(
            self._resolve(delivery_date=delivery).warnings,
            [
                f"Warning. Vendor price expires {self._fmt(end)}, before this "
                f"line's delivery date of {self._fmt(delivery)}."
            ],
        )

    def test_unpriced_remainder_is_unknown(self):
        self._set_stock_value(10.0)
        resolution = self._resolve(qty=60, qty_from_stock=40)
        self.assertEqual(resolution.confidence, "unknown")
        self.assertEqual(
            resolution.evidence[0],
            f"Firm. 40 of 60 covered from stock at {self._money(10.0)}; "
            "no known price for the balance.",
        )
        self.assertEqual(
            resolution.evidence[1], "Unknown. No vendor price for the other 20."
        )

    def test_dates_follow_the_user_language(self):
        end = fields.Date.today() + relativedelta(months=3)
        self._supplier_price(75.0, date_end=end)
        self.assertNotIn(fields.Date.to_string(end), self._resolve().evidence[0])
