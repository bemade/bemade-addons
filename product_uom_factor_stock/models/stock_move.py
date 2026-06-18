# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, models


class StockMove(models.Model):
    _name = "stock.move"
    _inherit = ["stock.move", "product.uom.factor.line.mixin"]

    # stock.move uses the field name `product_uom` (not `product_uom_id`).
    @api.constrains("product_uom", "product_id")
    def _check_factor_uom_allowed_stock_move(self):
        self._check_factor_uom_allowed("product_uom")
