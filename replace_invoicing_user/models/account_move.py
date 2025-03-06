from odoo import models, api, _
from odoo.tools import float_compare


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    def _get_mail_thread_data_for_subtype(self, subtype_id):
        # Surcharge de la méthode qui contrôle l'ajout des followers
        # Si no_follower_tracking est activé, on empêche l'ajout du follower par défaut
        if self.env.context.get('no_follower_tracking'):
            return []
        return super()._get_mail_thread_data_for_subtype(subtype_id)
    
    def message_subscribe(self, partner_ids=None, subtype_ids=None, email=True):
        # Empêcher l'ajout automatique de followers pour les factures si no_follower_tracking est activé
        if self._name == 'account.move' and self.env.context.get('no_follower_tracking'):
            # On ne permet l'ajout que de l'utilisateur spécifique
            specific_user_id = self.env.context.get('specific_invoice_user_id') or int(self.env['ir.config_parameter'].sudo().get_param(
                'current_user_as_invoice_user.specific_user_id', '0'
            ))
            if specific_user_id:
                specific_user = self.env['res.users'].browse(specific_user_id)
                if specific_user.exists() and specific_user.partner_id:
                    # On filtre pour ne garder que l'utilisateur spécifique dans les partner_ids
                    partner_ids = [pid for pid in partner_ids if pid == specific_user.partner_id.id] if partner_ids else []
                    # Si vide, on ne fait rien
                    if not partner_ids:
                        return True
            else:
                # Aucun utilisateur spécifique, on empêche l'ajout de followers
                return True
        return super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids, email=email)

    @api.model_create_multi
    def create(self, vals_list):
        # Modélisation des vals_list pour empêcher l'ajout des followers par défaut
        if self.env.context.get('no_follower_tracking'):
            for vals in vals_list:
                # Désactiver l'ajout automatique des followers lors de la création
                vals['message_follower_ids'] = []
                    
        # Créer les factures normalement avec le contexte approprié
        # Le contexte no_follower_tracking désactive l'ajout automatique du current_user via _get_mail_thread_data_for_subtype
        moves = super().create(vals_list)
        
        # Vérifier si on doit configurer des followers spécifiques
        if self.env.context.get('no_follower_tracking'):
            # Utiliser specific_invoice_user_id du contexte s'il existe, sinon lire depuis les paramètres
            specific_user_id = self.env.context.get('specific_invoice_user_id') or int(self.env['ir.config_parameter'].sudo().get_param(
                'current_user_as_invoice_user.specific_user_id', '0'
            ))
            
            # Récupérer l'utilisateur spécifique
            specific_user = None
            if specific_user_id:
                specific_user = self.env['res.users'].browse(specific_user_id)
                
            # Utiliser l'environnement superuser pour éviter les problèmes de droits
            # et traiter tous les moves d'un coup
            moves_sudo = moves.sudo()
            
            # D'abord, supprimer tous les followers pour tous les moves
            follower_model = self.env['mail.followers'].sudo()
            domain = [
                ('res_model', '=', 'account.move'),
                ('res_id', 'in', moves.ids)
            ]
            followers = follower_model.search(domain)
            if followers:
                followers.unlink()
                
            # Ensuite, ajouter l'utilisateur spécifique comme seul follower si nécessaire
            if specific_user and specific_user.exists() and specific_user.partner_id:
                for move in moves_sudo:
                    follower_model.create({
                        'partner_id': specific_user.partner_id.id,
                        'res_model': 'account.move',
                        'res_id': move.id
                    })
        
        return moves
