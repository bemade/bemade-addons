from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    picking_id = fields.One2many(
        comodel_name="stock.picking",
        string="Pickings",
        compute="_compute_picking_id",
    )

    @api.depends("invoice_line_ids.sale_line_ids.move_ids.picking_id")
    def _compute_picking_id(self):
        for move in self:
            pickings = move.invoice_line_ids.mapped("sale_line_ids.move_ids.picking_id")
            move.picking_id = pickings and pickings[0] or False
