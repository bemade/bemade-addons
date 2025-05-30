from odoo import models

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_create_commercial_invoice(self):
        """Create a commercial invoice from selected invoices."""
        commercial_invoice = self.env['commercial.invoice'].create_from_invoices(self)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'commercial.invoice',
            'res_id': commercial_invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }
