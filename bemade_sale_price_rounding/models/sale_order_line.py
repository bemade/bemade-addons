# -*- coding: utf-8 -*-
from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _get_display_price_ignore_combo(self):
        """Round the display price to currency precision.

        Multi-step pricelist chains (e.g. supplier cost → transport markup →
        public pricelist with discount) produce irrational intermediate values
        via currency conversions with ``round=False``.  The result bubbles up
        through ``_get_pricelist_price_before_discount()`` and ends up stored
        as 6+ decimal places on the SO line.

        Rounding here, at the last exit point before the price is committed to
        ``price_unit``, catches all code paths in a single override.
        """
        price = super()._get_display_price_ignore_combo()
        currency = (
            self.currency_id
            or self.company_id.currency_id
            or self.env.company.currency_id
        )
        return currency.round(price) if currency else price

    def _reset_price_unit(self):
        """Belt-and-suspenders: also round after full tax/UoM normalisation."""
        super()._reset_price_unit()
        currency = self.currency_id or self.company_id.currency_id
        if currency:
            self.price_unit = currency.round(self.price_unit)
            self.technical_price_unit = self.price_unit