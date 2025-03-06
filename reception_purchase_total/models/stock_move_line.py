from odoo import fields, models, api


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    picking_type_code = fields.Selection(
        related="picking_id.picking_type_id.code",
        string="Operation Type",
        store=True,
        readonly=True,
    )

    purchase_price_unit = fields.Float(
        string="Purchase Unit Price",
        related="move_id.purchase_price_unit",
        readonly=True,
        help="Unit price from the related purchase order line",
    )
    purchase_price_total = fields.Float(
        string="Purchase Total",
        compute="_compute_purchase_price_total",
        help="Total price for this move line based on purchase price and quantity",
    )
    purchase_currency_id = fields.Many2one(
        related="move_id.purchase_currency_id",
        string="Purchase Currency",
        readonly=True,
    )

    @api.depends("purchase_price_unit", "quantity")
    def _compute_purchase_price_total(self):
        for line in self:
            line.purchase_price_total = line.purchase_price_unit * line.quantity
