# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: a supplier price is as fresh as the last time it was confirmed.

Purchasers keep supplier prices current by editing them, not by filling in a
date. When the supplier price is tracked in its chatter, its history says when
the price last moved; other modules may know other confirmations (a dated
note, say) and add them through the extension point.

ACCEPTANCE CRITERIA
1. A tracked change of the price (or discount) 2 months ago makes the price
   Firm and reads "vendor price changed on {date}".
2. A tracked change of another field (minimum quantity, product code...) does
   not refresh the price.
3. Only an old tracked change: Estimated, naming that change.
4. With no tracked change, the line's creation dates the price
   ("vendor price entered on {date}"); write_date is never read.
5. Evidence dated after the day the cost is resolved for is ignored.
6. The most recent evidence wins, whoever contributed it: a module adding
   ``(date, basis)`` through ``_cost_source_seller_dates`` can make the price
   Firm, and words its basis in ``_cost_source_basis_text``.
7. The cost is the DISCOUNTED supplier price, per unit of the product (a
   price per box of 10 is divided by 10).
8. A supplier price in another currency shows its own figure first, with the
   conversion in brackets, both with their currency code:
   "Firm. 160.00 EUR (≈ 200.00 USD), vendor price changed on {date}."
   In the resolution's own currency, the usual amount is shown. Stock cost,
   kept in the company currency, reads the same way when the cost is asked
   in another currency ("Firm. Covered from stock at 10.00 USD (≈ 8.00 XCS).").
"""
from datetime import datetime, time, timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import NON_BREAKING_SPACE as NBSP

from odoo.addons.product_cost_source.models.product_product import ProductProduct

from .common import ProductCostSourceCommon


@tagged("-at_install", "post_install")
class TestSellerFreshness(ProductCostSourceCommon):
    def _track(self, seller, field_name, on, old=0.0, new=1.0):
        """A tracked change of ``field_name`` on ``seller``, logged on ``on``."""
        field = self.env["ir.model.fields"]._get("product.supplierinfo", field_name)
        self.env["mail.message"].create(
            {
                "model": "product.supplierinfo",
                "res_id": seller.id,
                "message_type": "notification",
                "date": datetime.combine(on, time(12, 0)),
                "tracking_value_ids": [
                    Command.create(
                        {
                            "field_id": field.id,
                            "old_value_float": old,
                            "new_value_float": new,
                        }
                    )
                ],
            }
        )

    def test_tracked_price_change_makes_it_firm(self):
        seller = self._supplier_price(75.0)
        changed = self._months_ago(2)
        self._track(seller, "price", changed, 70.0, 75.0)
        resolution = self._resolve()
        self.assertEqual(resolution.confidence, "firm")
        self.assertEqual(
            resolution.evidence,
            [f"Firm. {self._money(75.0)}, vendor price changed on {self._fmt(changed)}."],
        )

    def test_tracked_discount_change_counts(self):
        seller = self._supplier_price(75.0)
        self._track(seller, "discount", self._months_ago(1), 0.0, 5.0)
        self.assertEqual(self._resolve().confidence, "firm")

    def test_change_of_another_field_does_not_refresh(self):
        seller = self._supplier_price(75.0)
        self._track(seller, "min_qty", self._months_ago(1), 0.0, 1.0)
        resolution = self._resolve()
        self.assertEqual(resolution.confidence, "estimated")
        self.assertEqual(resolution.sources[0].basis, "entered")

    def test_only_an_old_change_is_estimated(self):
        seller = self._supplier_price(75.0)
        changed = self._months_ago(24)
        self._track(seller, "price", changed)
        self.assertEqual(
            self._resolve().evidence,
            [
                f"Estimated. {self._money(75.0)}, vendor price changed on "
                f"{self._fmt(changed)}, over 6 months ago. No contract in force."
            ],
        )

    def test_creation_dates_an_unchanged_price(self):
        entered = self._months_ago(10)
        self._supplier_price(75.0, entered=entered)
        resolution = self._resolve()
        self.assertEqual(resolution.confidence, "estimated")
        self.assertIn(
            f"vendor price entered on {self._fmt(entered)}", resolution.evidence[0]
        )

    def test_evidence_after_the_day_asked_is_ignored(self):
        seller = self._supplier_price(75.0)
        self._track(seller, "price", self._months_ago(1))
        resolution = self._resolve(date=self._months_ago(12))
        self.assertEqual(resolution.sources[0].basis, "entered")

    def test_contributed_evidence_makes_it_firm(self):
        self._supplier_price(75.0)
        confirmed = self._months_ago(1)
        original_dates = ProductProduct._cost_source_seller_dates
        original_text = ProductProduct._cost_source_basis_text

        def dates(product, seller):
            return original_dates(product, seller) + [(confirmed, "phoned")]

        def text(product, source):
            if source.basis == "phoned":
                return "confirmed by phone"
            return original_text(product, source)

        with patch.object(ProductProduct, "_cost_source_seller_dates", dates), patch.object(
            ProductProduct, "_cost_source_basis_text", text
        ):
            resolution = self._resolve()
        self.assertEqual(resolution.confidence, "firm")
        self.assertEqual(
            resolution.evidence, [f"Firm. {self._money(75.0)}, confirmed by phone."]
        )

    def test_cost_is_the_discounted_price_per_product_unit(self):
        box = self.env["uom.uom"].create(
            {
                "name": "Box of 10",
                "relative_factor": 10.0,
                "relative_uom_id": self.product.uom_id.id,
            }
        )
        self._supplier_price(200.0, discount=10.0, product_uom_id=box.id)
        self.assertAlmostEqual(self._resolve().unit_cost, 18.0)

    def _other_currency(self):
        usd = self.company.currency_id
        other = self.env["res.currency"].create(
            {"name": "XCS", "symbol": "¤", "rounding": 0.01}
        )
        self.env["res.currency.rate"].create(
            {
                "currency_id": other.id,
                "name": fields.Date.today() - timedelta(days=400),
                "company_id": self.company.id,
                # 1 company unit = 0.8 XCS, so 160 XCS = 200 company units
                "rate": 0.8 * (usd.with_company(self.company).rate or 1.0),
            }
        )
        return usd, other

    def test_stock_cost_shows_company_figure_first(self):
        usd, other = self._other_currency()
        self._set_stock_value(10.0)
        self.assertEqual(
            self._resolve(qty=5, qty_from_stock=5, currency=other).evidence,
            [f"Firm. Covered from stock at 10.00{NBSP}{usd.name} (≈ 8.00{NBSP}XCS)."],
        )

    def test_other_currency_shows_vendor_figure_first(self):
        usd, other = self._other_currency()
        seller = self._supplier_price(160.0, currency_id=other.id)
        changed = self._months_ago(1)
        self._track(seller, "price", changed)
        evidence = self._resolve().evidence
        self.assertEqual(
            evidence,
            [
                f"Firm. 160.00{NBSP}XCS (≈ 200.00{NBSP}{usd.name}), vendor price "
                f"changed on {self._fmt(changed)}."
            ],
        )
