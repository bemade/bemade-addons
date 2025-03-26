# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Model Synchronization Configuration for Bemade clients.

This module defines how models are synchronized between client instances
and the Bemade platform. It is simplified to focus on the specific needs
of Bemade clients.
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class OdooToBemadeCustomerSyncModel(models.Model):
    _name = 'odoo.to.bemade.customer.sync.model'
    _description = 'Modèle synchronisé avec Bemade'
    _inherit = 'odoo.sync.model'
    _order = 'priority, id'

    name = fields.Char(
        string='Nom',
        required=True,
        help='Nom descriptif du modèle synchronisé',
    )
    
    model = fields.Char(
        string='Modèle local',
        required=True,
        help='Nom technique du modèle local (ex: res.partner)',
    )
    
    bemade_model = fields.Char(
        string='Modèle Bemade',
        required=True,
        help='Nom technique du modèle correspondant chez Bemade',
    )
    
    config_id = fields.Many2one(
        comodel_name='odoo.to.bemade.customer.config',
        string='Configuration',
        required=True,
        ondelete='cascade',
    )
    
    active = fields.Boolean(
        string='Actif',
        default=True,
        help='Indique si ce modèle est synchronisé activement',
    )
    
    priority = fields.Integer(
        string='Priorité',
        default=10,
        help='Ordre de synchronisation (les valeurs plus élevées sont prioritaires)',
    )
    
    field_mapping = fields.Text(
        string='Mapping des champs',
        help='Mapping JSON des champs entre le modèle local et Bemade',
    )
    
    sync_domain = fields.Char(
        string='Domaine de synchronisation',
        default='[]',
        help='Domaine pour filtrer les enregistrements à synchroniser, au format JSON',
    )
    
    last_sync = fields.Datetime(
        string='Dernière synchronisation',
        readonly=True,
    )
    
    sync_status = fields.Selection(
        selection=[
            ('pending', 'En attente'),
            ('synced', 'Synchronisé'),
            ('error', 'Erreur')
        ],
        default='pending',
        string='Statut de synchronisation',
    )

    error_count = fields.Integer(
        string='Nombre d\'erreurs',
        default=0,
    )
    
    record_count = fields.Integer(
        string='Enregistrements synchronisés',
        compute='_compute_record_count',
    )
    
    @api.depends()
    def _compute_record_count(self):
        """Calcule le nombre d'enregistrements synchronisés pour ce modèle"""
        for record in self:
            try:
                model_obj = self.env[record.model]
                domain = eval(record.sync_domain)
                record.record_count = model_obj.search_count(domain)
            except Exception as e:
                _logger.error(f"Erreur lors du calcul du nombre d'enregistrements: {str(e)}")
                record.record_count = 0
    
    def action_sync_model(self):
        """Synchroniser ce modèle spécifique avec Bemade"""
        self.ensure_one()
        if not self.active:
            raise UserError(_("Ce modèle n'est pas actif pour la synchronisation."))
            
        # Obtenir la configuration
        config = self.config_id
        if not config or config.state != 'connected':
            raise UserError(_("La connexion avec Bemade n'est pas établie."))
            
        # Obtenir les enregistrements à synchroniser
        model_obj = self.env[self.model]
        domain = eval(self.sync_domain)
        records = model_obj.search(domain)
        
        # Queue des enregistrements pour synchronisation
        queue_obj = self.env['odoo.to.bemade.customer.sync.queue']
        count = 0
        
        for record in records:
            queue_obj.create({
                'model_id': self.id,
                'record_id': record.id,
                'operation': 'sync',
                'state': 'pending',
                'priority': self.priority,
            })
            count += 1
            
        # Mettre à jour le statut
        self.write({
            'last_sync': fields.Datetime.now(),
            'sync_status': 'pending',
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Synchronisation programmée'),
                'message': _(f"{count} enregistrements ont été mis en file d'attente pour la synchronisation."),
                'sticky': False,
                'type': 'success',
            }
        }
    
    def action_view_records(self):
        """Afficher les enregistrements correspondant à ce modèle"""
        self.ensure_one()
        return {
            'name': _('Enregistrements à synchroniser'),
            'type': 'ir.actions.act_window',
            'res_model': self.model,
            'view_mode': 'tree,form',
            'domain': self.sync_domain,
        }
        
    def action_view_queue(self):
        """Afficher les entrées de file d'attente pour ce modèle"""
        self.ensure_one()
        return {
            'name': _('File d\'attente de synchronisation'),
            'type': 'ir.actions.act_window',
            'res_model': 'odoo.to.bemade.customer.sync.queue',
            'view_mode': 'tree,form',
            'domain': [('model_id', '=', self.id)],
        }
