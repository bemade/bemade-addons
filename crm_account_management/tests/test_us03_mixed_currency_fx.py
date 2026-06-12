# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
# Author: Bemade Inc. (Marc Durepos <marc@bemade.org>)
"""
US-03: Bookings totals convert mixed-currency orders to the OU currency.

Acceptance criteria
-------------------
1. Booking totals convert each won order's amount to a common currency
   (OU currency_id) before summing when sources are mixed.  No more raw
   numeric summing of, e.g., USD + CAD into a CAD-only field.
2. Single-currency accounts are unaffected (no regression from _convert
   same-currency short-circuit).
3. Open-orders path (open_orders_amount) uses the same conversion helper.
"""
from datetime import date

from odoo.tests import tagged

from odoo.addons.crm_account_management.tests.common import OUTestCommon


@tagged("post_install", "-at_install")
class TestUS03MixedCurrencyFX(OUTestCommon):
    """
    US-03: Mixed-currency FX conversion for OU bookings / order metrics.

    Each test uses a known FX rate so expected values can be computed exactly.
    The company currency (whatever AccountTestInvoicingCommon sets up, typically
    USD) is used as the OU's ``currency_id``; a second currency (EUR) is set up
    with a well-known rate so assertions are deterministic.

    Rate setup: 1 EUR = 1.25 company-currency units.
    The ``rate`` field on ``res.currency.rate`` stores "units of this currency
    per 1 unit of company currency", so ``rate = 1 / 1.25 = 0.8``.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.ou_model = cls.env["organizational.unit"]

        # Create a test product used across all tests
        cls.product = cls.env["product.product"].create(
            {
                "name": "FX Test Product",
                "list_price": 100.0,
            }
        )

        # Set up a foreign currency: 1 EUR = 1.25 company-currency units.
        # rate = 0.8 means 0.8 EUR per 1 unit of company currency, so
        # inverse_rate = 1/0.8 = 1.25: 1 EUR converts to 1.25 company-currency.
        cls.foreign_currency = cls.setup_other_currency(
            "EUR",
            rates=[
                ("2000-01-01", 0.8),
            ],
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_company(self, name):
        """Create a top-level company partner (triggers OU auto-create)."""
        partner = self.partner_model.create({"name": name, "is_company": True})
        ou = self.ou_model.search([("owner_id", "=", partner.id)], limit=1)
        return partner, ou

    def _make_confirmed_order(self, partner, amount, currency=None, order_date=None):
        """Create and confirm a sale.order with a single line of the given amount.

        In Odoo 18, sale.order.currency_id is a stored computed field driven by the
        pricelist (``pricelist_id.currency_id``), so the currency cannot be set
        directly on the order.  When a non-default currency is requested, a throwaway
        pricelist in that currency is created and attached to the order so that
        ``_compute_currency_id`` picks it up correctly.
        """
        if order_date is None:
            order_date = date.today()
        vals = {
            "partner_id": partner.id,
            "date_order": order_date,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "product_uom_qty": 1,
                        "price_unit": amount,
                        "tax_id": False,
                    },
                )
            ],
        }
        if currency:
            # In Odoo 18, sale.order.currency_id is computed from the pricelist.
            # Create a pricelist in the requested currency so the order adopts it.
            pricelist = self.env["product.pricelist"].create({
                "name": f"Test pricelist {currency.name}",
                "currency_id": currency.id,
            })
            vals["pricelist_id"] = pricelist.id
        order = self.env["sale.order"].create(vals)
        order.action_confirm()
        return order

    # ------------------------------------------------------------------
    # Test 1: Mixed-currency won orders convert before summing
    # ------------------------------------------------------------------

    def test_won_quotations_amount_converts_mixed_currency(self):
        """
        AC-1: won_quotations_amount converts each order to the OU currency.

        One order is in the company currency (100 units) and one is in EUR
        (100 EUR).  With 1 EUR = 1.25 company-currency, the converted total
        must equal 100 + 125 = 225, NOT the raw numeric sum of 200.
        """
        partner, ou = self._make_company("FX Test Partner 1")

        # Order in company currency
        self._make_confirmed_order(partner, 100.0)
        # Order in EUR (100 EUR × 1.25 = 125 company-currency)
        self._make_confirmed_order(partner, 100.0, currency=self.foreign_currency)

        ou.invalidate_recordset()
        # Raw numeric sum would be 200; correctly converted total is 225.
        self.assertGreater(
            ou.won_quotations_amount,
            200.0,
            "Mixed-currency bookings must be converted before summing, not added numerically.",
        )
        self.assertAlmostEqual(
            ou.won_quotations_amount,
            225.0,
            places=2,
            msg="100 company-currency + 100 EUR@1.25 must equal 225 company-currency.",
        )

    # ------------------------------------------------------------------
    # Test 2: Single-currency total is unchanged
    # ------------------------------------------------------------------

    def test_single_currency_total_unchanged(self):
        """
        AC-2: When all orders share the OU currency, the total equals the raw sum.

        _convert short-circuits to identity when source == target, so no
        rounding or rate-table errors are introduced for single-currency accounts.
        """
        partner, ou = self._make_company("FX Test Partner 2")

        self._make_confirmed_order(partner, 100.0)
        self._make_confirmed_order(partner, 100.0)

        ou.invalidate_recordset()
        self.assertAlmostEqual(
            ou.won_quotations_amount,
            200.0,
            places=2,
            msg="Single-currency bookings must equal the exact sum without rounding deviation.",
        )

    # ------------------------------------------------------------------
    # Test 3: Open orders path also converts
    # ------------------------------------------------------------------

    def test_open_orders_amount_converts_mixed_currency(self):
        """
        AC-3: open_orders_amount converts each open order to the OU currency.

        One open order in company currency (100) and one in EUR (100 EUR),
        both not invoiced.  The reported amount must equal 225, not 200.
        """
        partner, ou = self._make_company("FX Test Partner 3")

        # Confirmed but not invoiced → open orders
        self._make_confirmed_order(partner, 100.0)
        self._make_confirmed_order(partner, 100.0, currency=self.foreign_currency)

        ou.invalidate_recordset()
        self.assertGreater(
            ou.open_orders_amount,
            200.0,
            "Mixed-currency open orders must be converted before summing.",
        )
        self.assertAlmostEqual(
            ou.open_orders_amount,
            225.0,
            places=2,
            msg="100 company-currency + 100 EUR@1.25 must equal 225 in open_orders_amount.",
        )
