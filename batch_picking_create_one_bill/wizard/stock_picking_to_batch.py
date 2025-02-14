from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPickingToBatch(models.TransientModel):
    _inherit = "stock.picking.to.batch"

    zero_quantity_default = fields.Boolean(
        string="Zero Quantity by Default",
        default=False,
        help="If checked, the default quantity for new move lines will be 0 instead of the computed quantity.",
    )

    def attach_pickings(self):
        self.ensure_one()
        # Pass zero_quantity_default through context to be handled in batch create
        return super(
            StockPickingToBatch,
            self.with_context(default_zero_quantity_default=self.zero_quantity_default),
        ).attach_pickings()
