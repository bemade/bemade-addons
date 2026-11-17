# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: an RFQ only counts as a quote once the vendor's price is in it.

When a purchaser asks a vendor for a price, Odoo fills the RFQ line with the
price already on file (the vendor's price list, converted to the RFQ's
currency and unit, or the product cost when the vendor has none). That figure
is our own number echoed back, not an answer.

ACCEPTANCE CRITERIA
1. An open RFQ whose line still carries the pre-filled vendor price is not
   Indicative: the confidence comes from the other evidence, and a note reads
   "Price requested on {RFQ} ({date}), no answer yet."
2. An open RFQ whose price was typed in (differs from the pre-fill) is
   Indicative, as before.
3. The pre-fill is recognised through a currency conversion (vendor price in
   another currency than the RFQ), even when the day's rate was loaded after
   the line was filled in (Odoo then used an earlier rate).
4. An RFQ line at zero is a request with no answer: noted, never Indicative.
5. With no vendor price on file, a line at the product's cost is the
   pre-fill too.
6. A pending request alone gives no price: the cost stays Unknown.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import PurchaseCostSourceCommon


@tagged("-at_install", "post_install")
class TestRfqPrefill(PurchaseCostSourceCommon):
    def _pending_note(self, rfq):
        on = fields.Datetime.context_timestamp(self.env.user, rfq.date_order).date()
        return f"Price requested on {rfq.name} ({self._fmt(on)}), no answer yet."

    def test_prefilled_rfq_is_not_indicative(self):
        self._supplier_price(50.0)
        rfq = self._order(None, state="sent")
        self.assertAlmostEqual(rfq.order_line.price_unit, 50.0)
        resolution = self._resolve()
        self.assertEqual(resolution.confidence, "estimated")
        self.assertAlmostEqual(resolution.unit_cost, 50.0)
        self.assertEqual(resolution.notes, [self._pending_note(rfq)])

    def test_typed_price_is_indicative(self):
        self._supplier_price(50.0)
        rfq = self._order(45.0, state="sent")
        resolution = self._resolve()
        self.assertEqual(resolution.confidence, "indicative")
        self.assertAlmostEqual(resolution.unit_cost, 45.0)
        self.assertEqual(
            resolution.evidence,
            [f"Indicative. Quoted {self._money(45.0)} on {rfq.name}, not yet confirmed."],
        )

    def test_prefill_recognised_through_a_currency_conversion(self):
        other = self.env["res.currency"].create(
            {"name": "XCR", "symbol": "¤", "rounding": 0.01}
        )
        self.env["res.currency.rate"].create(
            {
                "currency_id": other.id,
                "name": fields.Date.today() - timedelta(days=400),
                "company_id": self.company.id,
                "rate": 1.37 * (self.currency.with_company(self.company).rate or 1.0),
            }
        )
        self._supplier_price(165.29, currency_id=other.id)
        rfq = self._order(None, state="draft")
        self.assertNotAlmostEqual(rfq.order_line.price_unit, 165.29)
        # The day's own rate is loaded after the RFQ was filled in.
        self.env["res.currency.rate"].create(
            {
                "currency_id": other.id,
                "name": fields.Date.today(),
                "company_id": self.company.id,
                "rate": 1.40 * (self.currency.with_company(self.company).rate or 1.0),
            }
        )
        resolution = self._resolve()
        self.assertNotEqual(resolution.confidence, "indicative")
        self.assertEqual(resolution.notes, [self._pending_note(rfq)])

    def test_zero_priced_rfq_is_a_pending_request(self):
        self._supplier_price(50.0)
        rfq = self._order(0.0, state="draft")
        resolution = self._resolve()
        self.assertEqual(resolution.confidence, "estimated")
        self.assertEqual(resolution.notes, [self._pending_note(rfq)])

    def test_product_cost_is_the_prefill_without_vendor_price(self):
        self.product.standard_price = 30.0
        self._order(30.0, state="draft")
        self.assertNotEqual(self._resolve().confidence, "indicative")

    def test_pending_request_alone_is_unknown(self):
        self._order(0.0, state="draft")
        resolution = self._resolve()
        self.assertEqual(resolution.confidence, "unknown")
        self.assertEqual(resolution.sources, [])
