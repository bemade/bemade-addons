# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Bemade Synchronization Configuration.

This module handles the connection configuration specifically designed for
connecting to Odoo.bemade.org. It provides a simplified interface for clients
to establish and maintain a connection with the Bemade platform.
"""

import logging
import xmlrpc.client
import uuid

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

BEMADE_URL = "https://odoo.bemade.org"

class OdooToBemadeCustomerConfig(models.Model):
    """Bemade connection configuration.

    This model stores client-specific connection information for Bemade platform.
    It is designed to be simple and focused, with most parameters pre-configured.
    """

    _name = 'odoo.to.bemade.customer.config'
    _description = 'Configuration Bemade'

    name = fields.Char(
        string='Nom', 
        default='Connexion Bemade',
        readonly=True,
    )

    client_key = fields.Char(
        string='Clé Client', 
        required=True,
        help='Clé unique fournie par Bemade pour votre instance',
    )

    api_key = fields.Char(
        string='Clé API',
        required=True,
        help='Clé API fournie par Bemade pour l\'authentification',
    )
    
    company_name = fields.Char(
        string='Nom de l\'entreprise',
        help='Nom de votre entreprise tel qu\'il apparaît chez Bemade',
    )
    
    state = fields.Selection(
        selection=[
            ('draft', 'Non configuré'),
            ('testing', 'Test de connexion'),
            ('connected', 'Connecté'),
            ('error', 'Erreur')
        ], 
        default='draft', 
        string='État',
        readonly=True,
    )
    
    last_sync = fields.Datetime(
        string='Dernière synchronisation',
        readonly=True,
    )
    
    error_message = fields.Text(
        string='Message d\'erreur',
        readonly=True,
    )
    
    sync_models = fields.One2many(
        comodel_name='odoo.to.bemade.customer.sync.model', 
        inverse_name='config_id', 
        string='Modèles synchronisés',
        readonly=True,
    )
    
    instance_id = fields.Char(
        string='ID Instance',
        readonly=True,
        help='Identifiant unique de cette instance',
        default=lambda self: str(uuid.uuid4()),
    )
    
    active = fields.Boolean(
        string='Actif', 
        default=True,
    )
    
    auto_configure = fields.Boolean(
        string='Configuration automatique',
        default=True,
        help='Configurer automatiquement les modèles à synchroniser',
    )

    @api.model
    def create(self, vals):
        """Limiter à une seule configuration active"""
        existing = self.search([('active', '=', True)])
        if existing:
            raise UserError(_("Une configuration Bemade existe déjà. Vous ne pouvez avoir qu'une seule configuration active."))
        return super().create(vals)

    def test_connection(self):
        """Tester la connexion avec Bemade"""
        self.ensure_one()
        self.state = 'testing'
        try:
            # Endpoint spécifique pour valider les clés client
            common = xmlrpc.client.ServerProxy(f'{BEMADE_URL}/xmlrpc/2/common')
            result = common.validate_client(self.client_key, self.api_key, self.instance_id)
            
            if not result.get('success'):
                raise UserError(result.get('message', 'Échec de validation des clés'))
                
            # Mise à jour des informations
            self.write({
                'state': 'connected',
                'company_name': result.get('company_name', self.company_name),
                'error_message': False
            })
            
            # Si autoconfiguration est activée
            if self.auto_configure:
                self._configure_sync_models(result.get('models', []))
                
            return True
                
        except Exception as e:
            self.write({
                'state': 'error',
                'error_message': str(e)
            })
            return False

    def _configure_sync_models(self, models_data):
        """Configure les modèles à synchroniser basés sur les données de Bemade"""
        model_obj = self.env['client.bemade.sync.model']
        
        # Supprimer les anciens modèles
        self.sync_models.unlink()
        
        # Créer les nouveaux modèles
        for model_data in models_data:
            model_obj.create({
                'config_id': self.id,
                'name': model_data.get('name'),
                'model': model_data.get('model'),
                'bemade_model': model_data.get('bemade_model'),
                'active': True,
                'priority': model_data.get('priority', 10),
            })

    def get_connection(self):
        """Établir une connexion avec Bemade"""
        self.ensure_one()
        if self.state != 'connected':
            self.test_connection()
            if self.state != 'connected':
                raise UserError(f"Impossible de se connecter à Bemade: {self.error_message}")
        
        # Utiliser l'authentification par clé API
        common = xmlrpc.client.ServerProxy(f'{BEMADE_URL}/xmlrpc/2/common')
        uid = common.authenticate_client(self.client_key, self.api_key, self.instance_id)
        
        if not uid:
            raise UserError("Échec d'authentification avec Bemade")
            
        models = xmlrpc.client.ServerProxy(f'{BEMADE_URL}/xmlrpc/2/object')
        
        return models, uid
        
    def reset_configuration(self):
        """Réinitialiser la configuration"""
        self.ensure_one()
        return self.write({
            'state': 'draft',
            'error_message': False
        })
        
    def action_sync_now(self):
        """Déclencher une synchronisation immédiate"""
        self.ensure_one()
        if self.state != 'connected':
            raise UserError("Veuillez établir une connexion avant de synchroniser")
            
        # Appeler le gestionnaire de synchronisation
        return self.env['odoo.to.bemade.customer.sync.manager'].sync_all()
        
    @api.model
    def get_config(self):
        """Récupérer la configuration active"""
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            return False
        return config
