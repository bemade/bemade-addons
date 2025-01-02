from odoo import api, fields, models


class ResPartner(models.Model):
    """
    Extends the partner model to add sales cycle tracking functionality.
    """
    _inherit = 'res.partner'

    itch_cycle_product_ids = fields.One2many(
        comodel_name='itch.cycle.product.partner',
        inverse_name='partner_id',
        string="Product Sales Cycles",
        help="List of all product sales cycles associated with this customer",
    )

    reorder_cycle_product_ids = fields.One2many(
        comodel_name='itch.cycle.product.partner',
        inverse_name='partner_id',
        string="Active Sales Cycles",
        domain=[('quantity_of_orders', '>', 1)],
        help="List of product sales cycles with established patterns",
    )

    itch_next_delay = fields.Date(
        string="Next Follow-up Date",
        compute="_compute_itch_next_delay",
        store=True,
        help="Earliest follow-up date",
    )

    @api.depends(
        'itch_cycle_product_ids',
        'itch_cycle_product_ids.date_next_follow_up'
    )
    def _compute_itch_next_delay(self):
        """
        Compute the earliest follow-up date.
        
        The date is calculated from all associated product cycles.
        """
        for partner in self:
            cycles = partner.reorder_cycle_product_ids
            dates = cycles.mapped('date_next_follow_up')
            partner.itch_next_delay = min(dates) if dates else False

    def action_populate_itch_cycles(self):
        """
        Initialize or update product cycles.
        
        The cycles are created from historical order data.
        """
        self.env['itch.cycle.product.partner'].populate_from_past_orders()
