from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    purchase_price_unit = fields.Float(
        string="Purchase Unit Price",
        related="purchase_line_id.price_unit",
        digits="Product Price",
        readonly=True,
        help="Unit price from the related purchase order line",
    )
    purchase_price_total = fields.Float(
        string="Purchase Total",
        compute="_compute_purchase_price_total",
        help="Total price based on purchase unit price and move quantity",
    )
    picking_type_code = fields.Selection(
        related="picking_id.picking_type_code",
        readonly=True,
    )
    purchase_currency_id = fields.Many2one(
        related="purchase_line_id.currency_id",
        string="Purchase Currency",
        readonly=True,
    )

    @api.depends("purchase_price_unit", "quantity")
    def _compute_purchase_price_total(self):
        for move in self:
            move.purchase_price_total = move.purchase_price_unit * move.quantity
