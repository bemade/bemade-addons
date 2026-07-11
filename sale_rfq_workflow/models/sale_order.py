from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    supply_rfq_ids = fields.One2many(
        'purchase.order', 'supply_sale_order_id',
        string='Supply RFQs',
        copy=False,
    )
    supply_rfq_count = fields.Integer(compute='_compute_supply_rfq_count')

    @api.depends('supply_rfq_ids')
    def _compute_supply_rfq_count(self):
        for order in self:
            order.supply_rfq_count = len(order.supply_rfq_ids)

    def action_generate_supply_rfqs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.rfq.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sale_order_id': self.id},
        }

    def action_view_supply_rfqs(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('purchase.purchase_rfq')
        action['domain'] = [('supply_sale_order_id', '=', self.id)]
        action['context'] = {}
        if self.supply_rfq_count == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.supply_rfq_ids.id
        return action
