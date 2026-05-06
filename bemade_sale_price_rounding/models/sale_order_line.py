# -*- coding: utf-8 -*-
from odoo import models, fields


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    price_unit = fields.Float(digits="Product Price")