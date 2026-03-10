# -*- coding: utf-8 -*-
"""
Tests for bemade_sale_price_rounding

Use cases / acceptance criteria:

1. Percentage pricelist rule: when a pricelist applies a percentage discount
   to a product, the resulting price_unit on the sale order line must be
   rounded to the currency's rounding precision (e.g. 0.01 for USD/CAD).
   Example: $9.99 at 33% off → stored as 6.69, not 6.6933.

2. Formula pricelist rule (cost + markup): when a pricelist uses a formula
   based on cost, the resulting price_unit must similarly be rounded to
   currency precision.

3. Fixed pricelist price: a fixed price entered directly on a pricelist rule
   should be unaffected (it is already exact by definition).

4. Manual price override: if a user manually sets price_unit on a sale order
   line, the value should be preserved exactly as entered. This module only
   rounds prices that come from pricelist computation.

5. Multi-currency: rounding must use the *order's* currency precision, not the
   company currency. A foreign-currency order should round to that currency's
   precision.
"""
from odoo.fields import Command
from odoo.tests import Form, tagged

from odoo.addons.sale.tests.common import SaleCommon


@tagged("post_install", "-at_install")
class TestSalePriceRounding(SaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._enable_pricelists()

        # A product whose price produces non-round numbers under percentage rules.
        # 9.99 * (1 - 0.33) = 6.6933
        cls.product.lst_price = 9.99

        cls.pricelist = cls.env["product.pricelist"].create({
            "name": "Test Pricelist",
            "currency_id": cls.env.company.currency_id.id,
        })

    def _make_order(self, pricelist=None):
        pricelist = pricelist or self.pricelist
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": pricelist.id,
        })

    def _add_line(self, order, product=None, qty=1):
        product = product or self.product
        return self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": product.id,
            "product_uom_qty": qty,
        })

    def _assert_price_rounded(self, line):
        """Assert price_unit equals its currency-rounded value (exact equality)."""
        currency = line.currency_id
        rounded = currency.round(line.price_unit)
        self.assertEqual(
            line.price_unit,
            rounded,
            f"price_unit {line.price_unit} is not rounded to currency precision "
            f"({currency.name}, rounding={currency.rounding}); "
            f"expected {rounded}",
        )

    def test_percentage_pricelist_rounds_to_currency_precision(self):
        """price_unit is rounded to currency precision after a % pricelist rule."""
        self.env["product.pricelist.item"].create({
            "pricelist_id": self.pricelist.id,
            "compute_price": "percentage",
            "percent_price": 33,  # 9.99 * 0.67 = 6.6933
        })
        order = self._make_order()
        line = self._add_line(order)
        self._assert_price_rounded(line)

    def test_formula_pricelist_rounds_to_currency_precision(self):
        """price_unit is rounded to currency precision after a formula pricelist rule."""
        self.product.standard_price = 7.77
        self.env["product.pricelist.item"].create({
            "pricelist_id": self.pricelist.id,
            "compute_price": "formula",
            "base": "standard_price",
            "price_discount": -30,  # cost * 1.30 = 7.77 * 1.30 = 10.101
        })
        order = self._make_order()
        line = self._add_line(order)
        self._assert_price_rounded(line)

    def test_fixed_pricelist_price_unaffected(self):
        """A fixed pricelist price produces an exact price_unit with no unexpected rounding."""
        self.env["product.pricelist.item"].create({
            "pricelist_id": self.pricelist.id,
            "compute_price": "fixed",
            "fixed_price": 15.00,
        })
        order = self._make_order()
        line = self._add_line(order)
        self._assert_price_rounded(line)
        self.assertEqual(line.price_unit, 15.00)

    def test_manual_price_not_modified(self):
        """A manually set price_unit is not touched by this module."""
        order = self._make_order()
        line = self._add_line(order)
        line.price_unit = 12.345678
        self.assertEqual(line.price_unit, 12.345678)

    def test_multicurrency_uses_order_currency_rounding(self):
        """Rounding uses the order currency's precision, not the company currency's."""
        eur = self.env.ref("base.EUR")
        eur_pricelist = self.env["product.pricelist"].create({
            "name": "EUR Pricelist",
            "currency_id": eur.id,
        })
        self.env["product.pricelist.item"].create({
            "pricelist_id": eur_pricelist.id,
            "compute_price": "percentage",
            "percent_price": 33,  # 9.99 EUR * 0.67 → non-round
        })
        order = self._make_order(pricelist=eur_pricelist)
        line = self._add_line(order)
        self.assertEqual(line.currency_id, eur)
        self._assert_price_rounded(line)
