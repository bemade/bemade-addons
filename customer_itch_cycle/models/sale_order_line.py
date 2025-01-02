from odoo import models, fields, api


class SaleOrderLine(models.Model):
    """
    Extends sale order line to add itch cycle tracking.
    """
    _inherit = 'sale.order.line'

    itch_cycle_id = fields.Many2one(
        comodel_name='itch.cycle.product.partner',
        string="Cycle")

    stock_move_ids = fields.One2many(
        comodel_name='stock.move',
        inverse_name='sale_line_id',
        string="Movements")

    sale_date = fields.Datetime(
        string="Date",
        related='order_id.date_order',
        store=True)

    @api.model_create_multi
    def create(self, vals_list):
        """
        Create sale order lines and associate them with their itch cycle.
        
        If the product is cycle tracked and no existing cycle exists for the 
        product/partner combination, a new cycle is created.
        """
        lines = super().create(vals_list)

        for line in lines:
            if (line.product_id and line.order_id and
                    line.product_id.categ_id.is_cycle_tracked):
                partner_id = line.order_id.partner_id.id
                itch_cycle = self.env['itch.cycle.product.partner'].search([
                    ('partner_id', '=', partner_id),
                    ('product_id', '=', line.product_id.id)
                ], limit=1)
                if not itch_cycle:
                    cycle_vals = {
                        'partner_id': partner_id,
                        'product_id': line.product_id.id,
                    }
                    itch_cycle = self.env['itch.cycle.product.partner'].create(
                        cycle_vals)
                line.itch_cycle_id = itch_cycle.id

        return lines
