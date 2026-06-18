# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, models


class StockMoveLine(models.Model):
    _name = "stock.move.line"
    _inherit = ["stock.move.line", "product.uom.factor.line.mixin"]

    @api.constrains("product_uom_id", "product_id")
    def _check_factor_uom_allowed_stock_move_line(self):
        self._check_factor_uom_allowed("product_uom_id")
