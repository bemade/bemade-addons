# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: a confirmed purchase is the last known price.

ACCEPTANCE CRITERIA
1. A confirmed purchase order line within the price-age window is Firm and
   reads "Firm. Last purchased {date}."
2. One older than the window is Estimated and reads
   "Estimated. Last purchased {date}, over {n} months ago. No contract in
   force."
3. A purchase newer than a dated supplier price wins; an older one loses to it
   (the last known price is the more recent of the two).
4. A vendor price list in force (end date) still outranks a newer purchase.
5. Of several purchases, the latest confirmed one is used.
6. The price used is the discounted unit price, converted to the product's
   unit of measure, and to the requested currency at the purchase date.
7. A purchase confirmed after the date the cost is resolved for is ignored.
"""
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged

from .common import PurchaseCostSourceCommon


@tagged("-at_install", "post_install")
class TestPurchaseHistory(PurchaseCostSourceCommon):
    def test_recent_purchase_is_firm(self):
        on = self._months_ago(2)
        self._order(40.0, on=on)
        resolution = self._resolve()
        self.assertEqual(resolution.confidence, "firm")
        self.assertAlmostEqual(resolution.unit_cost, 40.0)
        self.assertEqual(resolution.evidence, [f"Firm. Last purchased {self._fmt(on)}."])

    def test_old_purchase_is_estimated(self):
        on = self._months_ago(8)
        self._order(40.0, on=on)
        resolution = self._resolve()
        self.assertEqual(resolution.confidence, "estimated")
        self.assertEqual(
            resolution.evidence,
            [
                f"Estimated. Last purchased {self._fmt(on)}, over 6 months ago. "
                "No contract in force."
            ],
        )

    def test_purchase_newer_than_supplier_price_wins(self):
        self._supplier_price(55.0, date_start=self._months_ago(10))
        self._order(40.0, on=self._months_ago(3))
        resolution = self._resolve()
        self.assertAlmostEqual(resolution.unit_cost, 40.0)
        self.assertEqual(resolution.confidence, "firm")

    def test_supplier_price_newer_than_purchase_wins(self):
        self._supplier_price(55.0, date_start=self._months_ago(1))
        self._order(40.0, on=self._months_ago(3))
        self.assertAlmostEqual(self._resolve().unit_cost, 55.0)

    def test_price_list_in_force_outranks_newer_purchase(self):
        self._supplier_price(
            55.0, date_end=fields.Date.today() + relativedelta(months=2)
        )
        self._order(40.0, on=fields.Date.today())
        resolution = self._resolve()
        self.assertAlmostEqual(resolution.unit_cost, 55.0)
        self.assertTrue(resolution.sources[0].in_force)

    def test_latest_purchase_is_used(self):
        self._order(30.0, on=self._months_ago(4))
        self._order(40.0, on=self._months_ago(1))
        self._order(35.0, on=self._months_ago(2))
        self.assertAlmostEqual(self._resolve().unit_cost, 40.0)

    def test_discount_and_unit_of_measure(self):
        dozen = self.env.ref("uom.product_uom_dozen")
        # 120 per dozen, 10 % off = 108 per dozen = 9 per unit.
        self._order(120.0, on=self._months_ago(1), uom=dozen, discount=10.0)
        self.assertAlmostEqual(self._resolve().unit_cost, 9.0)

    def test_currency_converted_at_purchase_date(self):
        other = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("id", "!=", self.currency.id)], limit=1)
        )
        other.active = True
        on = self._months_ago(2)
        self.env["res.currency.rate"].create(
            [
                {"name": on, "currency_id": other.id, "company_id": self.company.id, "rate": 2.0},
                {"name": fields.Date.today(), "currency_id": other.id, "company_id": self.company.id, "rate": 4.0},
            ]
        )
        self._order(100.0, on=on, currency=other)
        # 100 at 2 per unit of company currency on the purchase date == 50.
        self.assertAlmostEqual(self._resolve().unit_cost, 50.0, places=2)

    def test_purchase_after_the_resolution_date_is_ignored(self):
        self._order(40.0, on=self._months_ago(1))
        resolution = self._resolve(date=self._months_ago(2))
        self.assertEqual(resolution.sources, [])
