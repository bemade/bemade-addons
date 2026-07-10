from odoo import models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_analyse_quote(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.quote.analysis.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_purchase_order_id': self.id},
        }
