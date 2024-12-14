from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    itch_cycle_id = fields.Many2one(
        comodel_name='itch.cycle.product.partner',
        string="Cycle Produit/Partenaire"
    )

    @api.model
    def create(self, vals):
        line = super(SaleOrderLine, self).create(vals)
        # Associer au bon cycle produit/partenaire
        if vals.get('product_id') and vals.get('order_id'):
            partner_id = self.env['sale.order'].browse(vals['order_id']).partner_id.id
            itch_cycle = self.env['itch.cycle.product.partner'].search([
                ('partner_id', '=', partner_id),
                ('product_id', '=', vals['product_id'])
            ], limit=1)
            if not itch_cycle:
                itch_cycle = self.env['itch.cycle.product.partner'].create({
                    'partner_id': partner_id,
                    'product_id': vals['product_id'],
                })
            line.itch_cycle_id = itch_cycle.id
        return line