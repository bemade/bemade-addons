from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        
        # Get configuration parameters
        use_current_user = self.env['ir.config_parameter'].sudo().get_param(
            'current_user_as_invoice_user.use_current_user', 'True'
        ).lower() == 'true'
        
        specific_user_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'current_user_as_invoice_user.specific_user_id', '0'
        ))
        
        # Determine which user to use
        if use_current_user:
            user_id = self.env.user.id
        else:
            user_id = specific_user_id if specific_user_id else self.env.user.id
            
        invoice_vals.update({
            'invoice_user_id': user_id,
            'user_id': user_id,
        })
        return invoice_vals