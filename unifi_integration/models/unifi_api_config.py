# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class UnifiApiConfig(models.Model):
    """Configuration API pour le système UniFi
    
    Ce modèle stocke les configurations API pour les différents types d'API UniFi.
    Il centralise les paramètres de connexion et les options de sécurité.
    """
    _name = 'unifi.api.config'
    _description = 'UniFi API Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(
        string='Name',
        required=True,
        help='Nom de la configuration API'
    )
    
    api_type = fields.Selection(
        selection=[
            ('controller', 'UniFi Controller'),
            ('site_manager', 'UniFi Site Manager'),
        ],
        string='API Type',
        required=True,
        default='controller',
        help='Type d\'API UniFi'
    )
    
    controller_type = fields.Selection(
        selection=[
            ('udm', 'UniFi Dream Machine'),
            ('cloud_key', 'Cloud Key'),
            ('other', 'Other'),
        ],
        string='Controller Type',
        default='udm',
        help='Type de contrôleur UniFi (applicable uniquement pour le type d\'API Controller)',

    )
    
    base_url = fields.Char(
        string='Base URL',
        required=True,
        help='URL de base pour les appels API (ex: https://unifi.example.com)'
    )
    
    api_version = fields.Char(
        string='API Version',
        default='v1',
        help='Version de l\'API à utiliser'
    )
    
    username = fields.Char(
        string='Username',
        help='Nom d\'utilisateur pour l\'authentification API'
    )
    
    password = fields.Char(
        string='Password',
        help='Mot de passe pour l\'authentification API',

    )
    
    token = fields.Char(
        string='API Token',
        help='Jeton d\'authentification pour l\'API (si applicable)',

    )
    
    verify_ssl = fields.Boolean(
        string='Verify SSL',
        default=True,
        help='Vérifier les certificats SSL lors des appels API'
    )
    
    timeout = fields.Integer(
        string='Timeout',
        default=30,
        help='Délai d\'attente maximum pour les appels API (en secondes)'
    )
    
    retry_count = fields.Integer(
        string='Retry Count',
        default=3,
        help='Nombre de tentatives en cas d\'échec d\'un appel API'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Indique si cette configuration est active'
    )
    
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        help='Entreprise associée à cette configuration'
    )
    
    site_ids = fields.One2many(
        comodel_name='unifi.site',
        inverse_name='api_config_id',
        string='Sites',
        help='Sites utilisant cette configuration API',
        readonly=True  # Lecture seule car le champ n'existe pas encore dans unifi.site
    )
    
    log_ids = fields.One2many(
        comodel_name='unifi.api.log',
        inverse_name='api_config_id',
        string='API Logs',
        help='Journaux des appels API utilisant cette configuration',
        readonly=True  # Lecture seule car le champ n'existe pas encore dans unifi.api.log
    )
    
    notes = fields.Text(
        string='Notes',
        help='Notes additionnelles sur cette configuration API'
    )
    
    @api.constrains('base_url')
    def _check_base_url(self):
        """Vérifie que l'URL de base est valide"""
        for record in self:
            if not record.base_url:
                continue
                
            if not (record.base_url.startswith('http://') or record.base_url.startswith('https://')):
                raise ValidationError(_("L'URL de base doit commencer par 'http://' ou 'https://'."))
    
    def test_connection(self):
        """Teste la connexion à l'API UniFi"""
        self.ensure_one()
        
        try:
            # Logique de test de connexion selon le type d'API
            if self.api_type == 'controller':
                # Importer la classe UnifiClient
                from ..controllers.main import UnifiClient
                
                # Extraire le host et le port de l'URL de base
                from urllib.parse import urlparse
                parsed_url = urlparse(self.base_url)
                host = parsed_url.netloc.split(':')[0] if ':' in parsed_url.netloc else parsed_url.netloc
                port = parsed_url.port or 443
                
                # Créer une instance de l'API
                api = UnifiClient(
                    host=host,
                    port=port,
                    username=self.username,
                    password=self.password,
                    verify_ssl=self.verify_ssl
                )
                
                # Tester l'authentification
                if not api.login():
                    raise Exception(_("Échec de l'authentification au contrôleur UniFi"))
                    
                # Tester la récupération du statut du système
                try:
                    response = api._make_api_request('GET', api.API_SYSTEM_INFO_ENDPOINT)
                    if not response.ok:
                        raise Exception(_("Échec de la récupération du statut du système. Code: %s") % response.status_code)
                except Exception as e:
                    raise Exception(_("Échec de la récupération du statut du système: %s") % str(e))
                    
                # Pas besoin de déconnexion explicite avec cette API
                
            elif self.api_type == 'site_manager':
                # TODO(dev): Implémenter le test de connexion pour l'API Site Manager
                # Cette partie sera implémentée ultérieurement
                raise NotImplementedError(_("Le test de connexion pour l'API Site Manager n'est pas encore implémenté"))
                
            # Si on arrive ici, la connexion est réussie
            _logger.info("Connexion à l'API réussie pour %s", self.name)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Succès'),
                    'message': _('Connexion à l\'API réussie.'),
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            # En cas d'erreur, on affiche un message
            error_message = str(e)
            _logger.error("Échec de la connexion à l'API pour %s: %s", self.name, error_message)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('Échec de la connexion à l\'API: %s') % error_message,
                    'sticky': True,
                    'type': 'danger',
                }
            }
    
    def get_headers(self):
        """Retourne les en-têtes HTTP pour les appels API"""
        self.ensure_one()
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        
        # Ajouter le token d'authentification si disponible
        if self.token:
            if self.api_type == 'controller':
                headers['Authorization'] = f'Bearer {self.token}'
            elif self.api_type == 'site_manager':
                headers['X-Auth-Token'] = self.token
        
        return headers
    
    def encrypt_sensitive_data(self):
        """Chiffre les données sensibles (mot de passe, token)"""
        # Cette méthode pourrait être implémentée pour sécuriser davantage les données
        # en utilisant des mécanismes de chiffrement d'Odoo
        pass
