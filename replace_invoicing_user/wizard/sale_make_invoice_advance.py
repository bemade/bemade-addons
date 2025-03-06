from odoo import models


class SaleMakeInvoiceAdvance(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    def _prepare_invoice_values(self, order, so_line):
        invoice_vals = super()._prepare_invoice_values(order, so_line)
        
        # On utilise le contexte actuel qui doit déjà contenir les bonnes valeurs de _create_invoices
        use_current_user = self.env.context.get('use_current_user', self.env['ir.config_parameter'].sudo().get_param(
            'current_user_as_invoice_user.use_current_user', 'True'
        ).lower() == 'true')
        
        # Determine which user to use
        if use_current_user:
            # Utiliser l'utilisateur qui crée la facture
            user_id = self.env.uid
        else:
            # Utiliser l'utilisateur spécifique
            specific_user_id = self.env.context.get('specific_invoice_user_id') or int(self.env['ir.config_parameter'].sudo().get_param(
                'current_user_as_invoice_user.specific_user_id', '0'
            ))
            user_id = specific_user_id if specific_user_id else self.env.uid
            
        invoice_vals.update({
            'invoice_user_id': user_id,
            'user_id': user_id,
        })
        return invoice_vals
        
    def _create_invoices(self, sale_orders):
        # Gestion du contexte pour les followers et utilisateurs de facture
        use_current_user = self.env['ir.config_parameter'].sudo().get_param(
            'current_user_as_invoice_user.use_current_user', 'True'
        ).lower() == 'true'
        
        # Vérifier si on doit ajouter l'utilisateur courant comme follower
        current_user_as_follower = self.env['ir.config_parameter'].sudo().get_param(
            'current_user_as_invoice_user.current_user_as_follower', 'False'
        ).lower() == 'true'
        
        # Dans tous les cas, on utilise no_follower_tracking=True pour désactiver le comportement standard
        # et appliquer notre propre logique dans account_move.py
        ctx = {
            'no_follower_tracking': True,
            'use_current_user': use_current_user,
            'current_user_as_follower': current_user_as_follower,
            # Passer explicitement l'ID de l'utilisateur courant dans le contexte
            # Cela permet de garantir que c'est bien l'utilisateur spécifié dans with_user() qui est utilisé
            'explicit_user_id': self.env.user.id
        }
        
        if not use_current_user:
            # Si on utilise un utilisateur spécifique, on l'ajoute au contexte
            specific_user_id = int(self.env['ir.config_parameter'].sudo().get_param(
                'current_user_as_invoice_user.specific_user_id', '0'
            ))
            ctx['specific_invoice_user_id'] = specific_user_id
        
        self = self.with_context(**ctx)
        return super()._create_invoices(sale_orders)
