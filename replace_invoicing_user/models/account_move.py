from odoo import models, api, _
from odoo.tools import float_compare
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    def _get_mail_thread_data_for_subtype(self, subtype_id):
        # Surcharge de la méthode qui contrôle l'ajout des followers
        # Si no_follower_tracking est activé, on empêche l'ajout du follower par défaut
        if self.env.context.get('no_follower_tracking'):
            return []
        return super()._get_mail_thread_data_for_subtype(subtype_id)
    
    def message_subscribe(self, partner_ids=None, subtype_ids=None):
        # Empêcher l'ajout automatique de followers pour les factures si no_follower_tracking est activé
        if self._name == 'account.move' and self.env.context.get('no_follower_tracking'):
            # Vérifier si on doit ajouter l'utilisateur courant comme follower
            current_user_as_follower = self.env.context.get('current_user_as_follower')
            if current_user_as_follower is None:
                current_user_as_follower = self.env['ir.config_parameter'].sudo().get_param(
                    'current_user_as_invoice_user.current_user_as_follower', 'False'
                ).lower() == 'true'
            elif isinstance(current_user_as_follower, str):
                current_user_as_follower = current_user_as_follower.lower() == 'true'
            
            # Si l'ajout explicite de l'utilisateur courant est activé, permettre l'abonnement
            if current_user_as_follower and self.env.user.partner_id and partner_ids and self.env.user.partner_id.id in partner_ids:
                _logger.info(f"Allowing current user {self.env.user.display_name} to be added as follower via message_subscribe")
                # Ne filtrer que pour garder l'utilisateur courant
                partner_ids = [self.env.user.partner_id.id]
                return super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)
            
            # Pour les autres cas, vérifier l'utilisateur spécifique
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
                # Aucun utilisateur spécifique et pas d'ajout de l'utilisateur courant, on empêche l'ajout de followers
                return True
        return super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)

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
            # Vérifier si on utilise l'utilisateur courant ou un utilisateur spécifique
            use_current_user = self.env['ir.config_parameter'].sudo().get_param(
                'current_user_as_invoice_user.use_current_user', 'True'
            ).lower() == 'true'
            
            # Vérifier si on doit ajouter l'utilisateur courant comme follower
            # D'abord vérifier dans le contexte, puis dans les paramètres de configuration
            current_user_as_follower = self.env.context.get('current_user_as_follower')
            if current_user_as_follower is None:
                current_user_as_follower = self.env['ir.config_parameter'].sudo().get_param(
                    'current_user_as_invoice_user.current_user_as_follower', 'False'
                ).lower() == 'true'
            elif isinstance(current_user_as_follower, str):
                current_user_as_follower = current_user_as_follower.lower() == 'true'
            
            # Récupérer l'utilisateur courant pour éventuel ajout comme follower ou invoice_user_id
            # Priorité 1: Utiliser l'ID utilisateur explicite passé dans le contexte (depuis sale_make_invoice_advance.py)
            if self.env.context.get('explicit_user_id'):
                user_id = self.env.context.get('explicit_user_id')
                current_user = self.env['res.users'].browse(user_id)
            # Priorité 2: Récupérer l'utilisateur du contexte (si with_user a été utilisé)
            elif 'uid' in self._context:
                user_id = self._context.get('uid')
                current_user = self.env['res.users'].browse(user_id)
            # Priorité 3: Utiliser self._uid comme fallback
            else:
                current_user = self.env['res.users'].browse(self._uid)
            
            _logger.info(f"Context uid: {self._context.get('uid')}, env.uid: {self.env.uid}, self._uid: {self._uid}")
            _logger.info(f"Creating invoice with current_user: {current_user and current_user.display_name}")
            
            # Définir l'utilisateur à ajouter comme follower
            user_to_add = None
            
            # D'abord, supprimer tous les followers pour tous les moves pour partir d'une situation propre
            follower_model = self.env['mail.followers'].sudo()
            domain = [
                ('res_model', '=', 'account.move'),
                ('res_id', 'in', moves.ids)
            ]
            followers = follower_model.search(domain)
            if followers:
                followers.unlink()
            
            # Par défaut, pas d'utilisateur à ajouter
            user_to_add = None
            
            # Définir l'utilisateur de la facture selon la configuration
            for move in moves:
                if use_current_user:
                    # Définir invoice_user_id comme l'utilisateur courant
                    move.sudo().write({'invoice_user_id': current_user.id})
                else:
                    # Utiliser specific_invoice_user_id du contexte s'il existe, sinon lire depuis les paramètres
                    specific_user_id = self.env.context.get('specific_invoice_user_id') or int(self.env['ir.config_parameter'].sudo().get_param(
                        'current_user_as_invoice_user.specific_user_id', '0'
                    ))
                    
                    if specific_user_id:
                        # Ajouter l'utilisateur spécifique comme invoice_user_id
                        move.sudo().write({'invoice_user_id': specific_user_id})
            
            # Déterminer quel utilisateur ajouter comme follower
            if use_current_user and current_user_as_follower and current_user and current_user.exists() and current_user.partner_id:
                # Si on utilise l'utilisateur courant et qu'on doit l'ajouter comme follower
                user_to_add = current_user
            elif not use_current_user:
                # Si on utilise un utilisateur spécifique
                specific_user_id = self.env.context.get('specific_invoice_user_id') or int(self.env['ir.config_parameter'].sudo().get_param(
                    'current_user_as_invoice_user.specific_user_id', '0'
                ))
                
                if specific_user_id:
                    user_to_add = self.env['res.users'].browse(specific_user_id)
            
            # Ensuite, ajouter l'utilisateur approprié comme seul follower si nécessaire
            # Journalisation pour faciliter le débogage
            _logger.info(f"User to add: {user_to_add and user_to_add.display_name}, current_user_as_follower: {current_user_as_follower}")
            
            if use_current_user and current_user_as_follower:
                # Si on a explicitement configuré d'ajouter l'utilisateur courant comme follower
                for move in moves:
                    # Créer le follower directement avec le modèle mail.followers
                    if current_user and current_user.partner_id:
                        _logger.info(f"Subscribing user {current_user.display_name} to move {move.id}")
                        # Vérifier si le follower existe déjà avant de le créer
                        existing_follower = follower_model.search([
                            ('partner_id', '=', current_user.partner_id.id),
                            ('res_model', '=', 'account.move'),
                            ('res_id', '=', move.id)
                        ])
                        
                        if not existing_follower:
                            # Créer le follower manuellement
                            follower = follower_model.create({
                                'partner_id': current_user.partner_id.id,
                                'res_model': 'account.move',
                                'res_id': move.id,
                                'subtype_ids': [(6, 0, [self.env.ref('mail.mt_comment').id])]
                            })
                            _logger.info(f"Follower created with ID: {follower.id}")
            elif user_to_add and user_to_add.exists() and user_to_add.partner_id:
                # Pour les autres cas où on a déterminé un utilisateur à ajouter
                for move in moves:
                    _logger.info(f"Subscribing specific user {user_to_add.display_name} to move {move.id}")
                    # Vérifier si le follower existe déjà avant de le créer
                    existing_follower = follower_model.search([
                        ('partner_id', '=', user_to_add.partner_id.id),
                        ('res_model', '=', 'account.move'),
                        ('res_id', '=', move.id)
                    ])
                    
                    if not existing_follower:
                        # Créer le follower manuellement
                        follower = follower_model.create({
                            'partner_id': user_to_add.partner_id.id,
                            'res_model': 'account.move',
                            'res_id': move.id,
                            'subtype_ids': [(6, 0, [self.env.ref('mail.mt_comment').id])]
                        })
                        _logger.info(f"Specific user follower created with ID: {follower.id}")
            
            # S'assurer que les followers sont correctement ajoutés
            self.env.cr.flush()
        
        return moves
