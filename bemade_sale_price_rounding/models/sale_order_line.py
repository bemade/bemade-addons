# -*- coding: utf-8 -*-
from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _reset_price_unit(self):
        super()._reset_price_unit()
        currency = self.currency_id or self.company_id.currency_id
        self.price_unit = currency.round(self.price_unit)
        self.technical_price_unit = self.price_unit
