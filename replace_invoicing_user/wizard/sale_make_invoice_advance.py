from odoo import models


class SaleMakeInvoiceAdvance(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    def _prepare_invoice_values(self, order, so_line):
        invoice_vals = super()._prepare_invoice_values(order, so_line)
        
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
            # Ne pas tracker les followers si on n'utilise pas l'utilisateur courant
            # Cette valeur sera lue depuis le contexte par le modèle account.move
            self = self.with_context(no_follower_tracking=True, specific_invoice_user_id=specific_user_id)
            
        invoice_vals.update({
            'invoice_user_id': user_id,
            'user_id': user_id,
        })
        return invoice_vals
        
    def _create_invoices(self, sale_orders):
        # Si on utilise un utilisateur spécifique, il faut aussi passer le contexte ici
        use_current_user = self.env['ir.config_parameter'].sudo().get_param(
            'current_user_as_invoice_user.use_current_user', 'True'
        ).lower() == 'true'
        
        if not use_current_user:
            specific_user_id = int(self.env['ir.config_parameter'].sudo().get_param(
                'current_user_as_invoice_user.specific_user_id', '0'
            ))
            self = self.with_context(no_follower_tracking=True, specific_invoice_user_id=specific_user_id)
            
        return super()._create_invoices(sale_orders)
