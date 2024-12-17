from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    itch_cycle_id = fields.Many2one(
        comodel_name='itch.cycle.product.partner',
        string="Cycle Produit/Partenaire"
    )

    stock_move_ids = fields.One2many(
        comodel_name='stock.move',
        inverse_name='sale_line_id',
        string="Mouvements de stock"
    )

    sale_date = fields.Datetime(
        string="Date de vente",
        related='order_id.date_order',
        store=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        # Appeler le super pour créer les lignes
        lines = super().create(vals_list)

        # Associer les lignes nouvellement créées avec leur cycle
        for line in lines:
            if line.product_id and line.order_id:
                partner_id = line.order_id.partner_id.id
                itch_cycle = self.env['itch.cycle.product.partner'].search([
                    ('partner_id', '=', partner_id),
                    ('product_id', '=', line.product_id.id)
                ], limit=1)
                if not itch_cycle:
                    itch_cycle = self.env['itch.cycle.product.partner'].create({
                        'partner_id': partner_id,
                        'product_id': line.product_id.id,
                    })
                line.itch_cycle_id = itch_cycle.id

        return lines