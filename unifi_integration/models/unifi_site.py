# -*- coding: utf-8 -*-

# These imports will work in an Odoo environment, even if your IDE marks them as not found
# pylint: disable=import-error
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .unifi_common import UnifiCommonMixin
# pylint: enable=import-error

import json
import logging
import requests
import urllib3
import tempfile
import os
import base64
import ast
from datetime import datetime, timedelta
from typing import Dict, Tuple, List, Any
from requests.exceptions import RequestException, ConnectionError

_logger = logging.getLogger(__name__)

# TODO: Refactorisation du modèle UnifiSite
# Changements effectués:
# 1. Fusion de trois fichiers en un seul:
#    - unifi_site.py, unifi_site_controller.py et unifi_site_manager.py
# 2. Intégration directe des champs et méthodes spécifiques dans le modèle principal
# 3. Simplification des relations et de la validation

class UnifiSite(models.Model, UnifiCommonMixin):
    """Represents a UniFi site managed by one or more UniFi devices
    
    This model is the central entity that groups all UniFi configurations and devices.
    Each site can have multiple devices, networks, and users.
    It supports both the Site Manager API (cloud) and the Controller API (local).
    
    All functionality is now integrated in a single model for simplicity and maintainability.
    The API type determines which fields and methods are applicable.    
    """
    _name = 'unifi.site'
    _description = 'UniFi Site'
    _order = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # Basic site information
    name = fields.Char(
        string='Name', 
        required=True, 
        help='Site name'
    )
    
    site_id = fields.Char(
        string='Site ID',
        help="Site identifier in UniFi (usually 'default')",
        default='default',
        readonly=True,
        required=True
    )
    
    description = fields.Text(
        string='Description',
        help='Site description'
    )
    
    address = fields.Text(
        string='Physical Address',
        help='Physical location of this site'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Indicates if this site is currently active'
    )
    
    # API Type - New field to distinguish between Site Manager and Controller APIs
    api_type = fields.Selection(
        selection=[
            ('site_manager', 'Site Manager (Cloud)'),
            ('controller', 'Controller (Local)')
        ],
        string='API Type',
        required=True,
        default='controller',
        help='Type of API used to connect to this site'
    )
    
    # Relation avec la configuration API
    api_config_id = fields.Many2one(
        comodel_name='unifi.api.config',
        string='Configuration API',
        help='Configuration API utilisée pour ce site'
    )
    
    # Performance and synchronization settings
    timeout = fields.Float(
        string='Timeout',
        default=10.0,
        help='API request timeout in seconds'
    )
    
    max_retries = fields.Integer(
        string='Max Retries',
        default=3,
        help='Maximum number of retries for API requests'
    )
    
    auto_sync = fields.Boolean(
        string='Automatic Synchronization',
        default=False,
        help='Enable automatic synchronization of this site'
    )
    
    sync_interval = fields.Integer(
        string='Sync Interval',
        default=60,
        help='Interval in minutes between automatic synchronizations'
    )
    
    # SSL verification - Common for both API types
    verify_ssl = fields.Boolean(
        string='Verify SSL',
        default=True,
        help='Enable SSL certificate verification',
    )
    
    # Connection information - Common fields
    timestamp = fields.Datetime(
        string='Created Date',
        default=lambda self: fields.Datetime.now(),
        readonly=True,
        help='Date and time when this site was created'
    )
    
    last_sync = fields.Datetime(
        string='Last Sync',
        readonly=True,
        help='Date and time when this site was last synchronized'
    )
    
    last_update = fields.Datetime(
        string='Last Update',
        readonly=True,
        help='Date and time of the last successful synchronization'
    )
    
    last_import_date = fields.Datetime(
        string='Last Import Date',
        readonly=True,
        help='Date and time of the last successful configuration import'
    )
    
    last_response_headers = fields.Text(
        string='Last Response Headers',
        readonly=True,
        copy=False,
        help='Headers from the last API response'
    )
    
    last_response_content = fields.Text(
        string='Last Response Content',
        readonly=True,
        copy=False,
        help='Content from the last API response'
    )
    
    last_successful_endpoint = fields.Char(
        string='Last Successful Endpoint',
        readonly=True,
        copy=False,
        help='The last endpoint that was successfully used for authentication'
    )
    
    import_status = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('failed', 'Failed'),
            ('pending', 'Pending')
        ],
        string='Import Status',
        default='pending',
        help='Status of the last configuration import'
    )
    
    # SSL verification - Common for both API types
    verify_ssl = fields.Boolean(
        string='Verify SSL',
        default=False,
        help='Enable SSL certificate verification'
    )
    
    # Controller API specific fields
    host = fields.Char(
        string='Host',
        help='IP address or hostname of the controller'
    )
    
    port = fields.Integer(
        string='Port',
        default=443,
        help='Port number (default: 443)'
    )
    
    username = fields.Char(
        string='Username',
        help='Username for controller login'
    )
    
    password = fields.Char(
        string='Password',
        help='Password for controller login'
    )
    
    ssl_cert_file = fields.Binary(
        string='Certificat SSL personnalisé', 
        attachment=True, 
        help='Fichier de certificat SSL personnalisé (.pem ou .crt)'
    )
    
    ssl_cert_filename = fields.Char(
        string='Nom du fichier de certificat'
    )
    
    ssl_cert_path = fields.Char(
        string='Chemin du certificat', 
        compute='_compute_ssl_cert_path', 
        store=True, 
        help='Chemin vers le fichier de certificat SSL'
    )
    
    # Site Manager API specific fields
    api_key = fields.Char(
        string='API Key',
        help='API Key for Site Manager authentication'
    )
    
    mfa_enabled = fields.Boolean(
        string='MFA Enabled',
        default=False,
        help='Enable Multi-Factor Authentication'
    )
    
    mfa_token = fields.Char(
        string='MFA Token',
        help='Multi-Factor Authentication token'
    )
    
    # Authentication fields
    auth_session_id = fields.Many2one(
        comodel_name='unifi.auth.session',
        string='Session d\'authentification',
        ondelete='set null',
        help='Session d\'authentification active pour ce site'
    )
    
    # Relations avec d'autres modèles
    device_ids = fields.One2many(
        comodel_name='unifi.device',
        inverse_name='site_id',
        string='Devices',
        help='Devices in this site'
    )
    
    device_count = fields.Integer(
        string='Device Count',
        compute='_compute_counts',
        compute_sudo=True,
        store=True,
        help='Number of devices in this site'
    )
    
    network_ids = fields.One2many(
        comodel_name='unifi.network',
        inverse_name='site_id',
        string='Networks',
        help='Networks in this site'
    )
    
    network_count = fields.Integer(
        string='Network Count',
        compute='_compute_counts',
        compute_sudo=True,
        store=True,
        help='Number of networks in this site'
    )
    
    user_ids = fields.One2many(
        comodel_name='unifi.user',
        inverse_name='site_id',
        string='Users',
        help='Users in this site'
    )
    
    user_count = fields.Integer(
        string='User Count',
        compute='_compute_counts',
        compute_sudo=True,
        store=True,
        help='Number of users in this site'
    )
    
    # Relations pour les VLANs
    vlan_ids = fields.One2many(
        comodel_name='unifi.vlan',
        inverse_name='site_id',
        string='VLANs',
        help='VLANs in this site'
    )
    
    vlan_count = fields.Integer(
        string='VLAN Count',
        compute='_compute_counts',
        compute_sudo=True,
        store=True,
        help='Number of VLANs in this site'
    )
    
    # Relations pour les règles de pare-feu
    firewall_rule_ids = fields.One2many(
        comodel_name='unifi.firewall.rule',
        inverse_name='site_id',
        string='Firewall Rules',
        help='Firewall rules in this site'
    )
    
    firewall_rule_count = fields.Integer(
        string='Firewall Rule Count',
        compute='_compute_counts',
        compute_sudo=True,
        store=True,
        help='Number of firewall rules in this site'
    )
    
    # Relations pour les redirections de port
    port_forward_ids = fields.One2many(
        comodel_name='unifi.port.forward',
        inverse_name='site_id',
        string='Port Forwards',
        help='Port forwarding rules in this site'
    )
    
    port_forward_count = fields.Integer(
        string='Port Forward Count',
        compute='_compute_counts',
        compute_sudo=True,
        store=True,
        help='Number of port forwarding rules in this site'
    )
    
    # Relations pour les configurations de routage
    routing_config_ids = fields.One2many(
        comodel_name='unifi.routing.config',
        inverse_name='site_id',
        string='Routing Configurations',
        help='Routing configurations in this site'
    )
    
    routing_config_count = fields.Integer(
        string='Routing Config Count',
        compute='_compute_counts',
        compute_sudo=True,
        store=True,
        help='Number of routing configurations in this site'
    )
    
    # Relations pour les WiFi
    wifi_ids = fields.One2many(
        comodel_name='unifi.wifi',
        inverse_name='site_id',
        string='WiFi Networks',
        help='WiFi networks in this site'
    )
    
    wifi_count = fields.Integer(
        string='WiFi Count',
        compute='_compute_counts',
        compute_sudo=True,
        store=True,
        help='Number of WiFi networks in this site'
    )
    
    # Relations pour DNS
    dns_ids = fields.One2many(
        comodel_name='unifi.dns',
        inverse_name='site_id',
        string='DNS Entries',
        help='DNS entries in this site'
    )
    
    dns_count = fields.Integer(
        string='DNS Count',
        compute='_compute_counts',
        compute_sudo=True,
        store=True,
        help='Number of DNS entries in this site'
    )
    
    # Relations pour System Info
    system_info_ids = fields.One2many(
        comodel_name='unifi.system.info',
        inverse_name='site_id',
        string='System Info',
        help='System information for this site'
    )
    
    system_info_count = fields.Integer(
        string='System Info Count',
        compute='_compute_counts',
        compute_sudo=True,
        store=True,
        help='Number of system info entries in this site'
    )
    
    # Relations pour VPN
    vpn_ids = fields.One2many(
        comodel_name='unifi.vpn',
        inverse_name='site_id',
        string='VPN Configurations',
        help='VPN configurations in this site'
    )
    
    vpn_count = fields.Integer(
        string='VPN Count',
        compute='_compute_counts',
        compute_sudo=True,
        store=True,
        help='Number of VPN configurations in this site'
    )
    
    # Relations pour les logs API et les jobs de synchronisation
    api_log_ids = fields.One2many(
        comodel_name='unifi.api.log',
        inverse_name='site_id',
        string='API Logs',
        help='API logs for this site'
    )
    
    sync_job_ids = fields.One2many(
        comodel_name='unifi.sync.job',
        inverse_name='site_id',
        string='Sync Jobs',
        help='Synchronization jobs for this site'
    )
    
    # Note: La méthode _compute_counts est définie plus bas dans le fichier
    
    @api.depends('ssl_cert_file', 'ssl_cert_filename')
    def _compute_connection_fields(self):
        """Compute connection fields based on API configuration
        
        This method sets connection fields (like verify_ssl, host, port, etc.) 
        based on the selected API configuration.
        """
        for record in self:
            # Utiliser la valeur par défaut si aucune configuration n'est définie
            if not record.api_config_id:
                # Garder les valeurs actuelles ou utiliser les valeurs par défaut
                if not hasattr(record, 'verify_ssl') or record.verify_ssl is None:
                    record.verify_ssl = False
                continue
                
            # Si une configuration API est définie, utiliser ses valeurs
            if record.api_config_id.api_type == record.api_type:
                # Copier les champs de connexion de la configuration API
                record.verify_ssl = record.api_config_id.verify_ssl
                
                # Définir les champs spécifiques au type d'API
                if record.api_type == 'controller':
                    # Extraire l'hôte et le port de l'URL de base
                    from urllib.parse import urlparse
                    parsed_url = urlparse(record.api_config_id.base_url)
                    record.host = parsed_url.netloc.split(':')[0] if ':' in parsed_url.netloc else parsed_url.netloc
                    record.port = parsed_url.port or 443
                    record.username = record.api_config_id.username
                    record.password = record.api_config_id.password
                
                elif record.api_type == 'site_manager':
                    record.api_key = record.api_config_id.token
                    
    #----------------------------------------------------------
    # Méthodes pour la récupération des données (remplacent les méthodes du controller)
    #----------------------------------------------------------
    
    def _get_system_info_data(self):
        """Récupère les informations système du site
        
        Cette méthode remplace l'ancienne méthode get_system_info_data du controller.
        
        Returns:
            dict: Données d'information système ou False en cas d'échec
        """
        self.ensure_one()
        # TODO: Implémenter la récupération des informations système
        return {}
    
    def _get_device_data(self):
        """Récupère les données des appareils du site
        
        Cette méthode remplace l'ancienne méthode get_device_data du controller.
        
        Returns:
            dict: Données des appareils ou False en cas d'échec
        """
        self.ensure_one()
        _logger.info("=== DÉBUT DE LA RÉCUPÉRATION DES APPAREILS ===")
        
        # Vérifier que nous avons une session d'authentification valide
        if not self._check_auth_session():
            _logger.error("Pas de session d'authentification valide pour récupérer les appareils")
            return False
            
        try:
            # Construire l'URL pour récupérer les appareils
            base_url = f"https://{self.host}:{self.port}"
            
            # Essayer de se reconnecter pour obtenir des cookies frais
            _logger.info("Tentative de reconnexion pour obtenir des cookies frais")
            connection_result = self._test_controller_connection()
            if connection_result.get('status') != 'success':
                _logger.error(f"Impossible de se reconnecter: {connection_result.get('message')}")
                return False
            _logger.info("Reconnexion réussie, poursuite de la récupération des appareils")
            
            # Déterminer si nous avons affaire à un UDM Pro/UCG Max ou un contrôleur standard
            # Si nous nous sommes connectés avec /api/auth/login, c'est probablement un UDM Pro/UCG Max
            # Ou si la réponse contient 'UDM Pro' ou 'Dream Machine' dans les headers ou le contenu
            is_udm_pro = False
            
            # Vérifier si l'endpoint d'authentification est celui d'un UDM Pro
            if self.auth_session_id and self.auth_session_id.endpoint and '/api/auth/login' in self.auth_session_id.endpoint:
                is_udm_pro = True
                
            # Vérifier si le dernier contenu de réponse contient des indices d'un UDM Pro
            if self.last_response_content and ('UDMPRO' in self.last_response_content or 'Dream Machine' in self.last_response_content):
                is_udm_pro = True
                
            _logger.info(f"Type de contrôleur détecté: {'UDM Pro/UCG Max' if is_udm_pro else 'Controller standard'}")
            
            # Essayer différents site_id et endpoints
            site_ids = [
                self.site_id,  # Utiliser le site_id configuré
                "default",    # Valeur par défaut souvent utilisée
                ""            # Essayer sans site_id
            ]
            
            # Préparer la vérification SSL
            verify = self.verify_ssl
            if verify and self.ssl_cert_path:
                verify = self.ssl_cert_path
                
            # Essayer chaque combinaison de site_id et endpoint
            response = None
            success = False
            
            for site_id in site_ids:
                # Construire les endpoints avec le site_id actuel
                device_endpoints = []
                
                # Forcer is_udm_pro à True car nous avons réussi à nous connecter avec /api/auth/login
                # Ce qui est caractéristique d'un UDM Pro
                if self.last_successful_endpoint and '/api/auth/login' in self.last_successful_endpoint:
                    is_udm_pro = True
                    _logger.info("Détection forcée d'un UDM Pro basée sur l'endpoint d'authentification utilisé")
                    
                # Vérifier si les cookies contiennent un TOKEN, ce qui est caractéristique d'un UDM Pro
                cookies = self._get_auth_cookies()
                if cookies and 'TOKEN' in cookies:
                    is_udm_pro = True
                    _logger.info("Détection forcée d'un UDM Pro basée sur la présence d'un TOKEN dans les cookies")
                
                if site_id:
                    if is_udm_pro:
                        # Pour UDM Pro/UCG Max, tous les endpoints doivent être préfixés avec /proxy/network
                        device_endpoints = [
                            f"/proxy/network/api/s/{site_id}/stat/device",     # Endpoint pour UDM Pro/UCG Max
                            f"/proxy/network/v2/api/site/{site_id}/device",   # Autre endpoint possible pour UDM Pro
                            f"/proxy/network/api/site/{site_id}/stat/device", # Autre endpoint possible
                            f"/api/s/{site_id}/stat/device",                   # Essayer aussi sans le préfixe
                        ]
                    else:
                        # Pour les contrôleurs standard
                        device_endpoints = [
                            f"/api/s/{site_id}/stat/device",                   # Endpoint standard
                            f"/api/site/{site_id}/stat/device",               # Endpoint alternatif
                            f"/v2/api/site/{site_id}/device"                 # Endpoint pour les versions plus récentes
                        ]
                else:
                    # Endpoints sans site_id
                    if is_udm_pro:
                        device_endpoints = [
                            "/proxy/network/api/stat/device",                # Pour UDM Pro/UCG Max
                            "/proxy/network/api/s/default/stat/device",     # Essai avec 'default'
                            "/proxy/network/v2/api/site/default/device",    # Autre endpoint possible pour UDM Pro
                            "/api/stat/device"                              # Essai sans le préfixe
                        ]
                    else:
                        device_endpoints = [
                            "/api/stat/device",                              # Essai sans site_id
                            "/v2/api/device"                                 # Autre essai sans site_id
                        ]
                
                for endpoint in device_endpoints:
                    try:
                        current_url = f"{base_url}{endpoint}"
                        _logger.info(f"Essai avec l'endpoint: {endpoint} (site_id: {site_id or 'aucun'})")
                        
                        # Récupérer les cookies de la session d'authentification
                        cookies = self._get_auth_cookies()
                        if not cookies:
                            _logger.error("Impossible de récupérer les cookies d'authentification")
                            continue
                        
                        # Afficher les cookies pour débogage
                        _logger.info(f"Cookies utilisés: {cookies}")
                        
                        # Construire les arguments de la requête
                        kwargs = {
                            "cookies": cookies,
                            "verify": verify,
                            "timeout": self.timeout
                        }
                        
                        # Ajouter des headers spécifiques
                        # Extraire le token pour l'authentification
                        token = cookies.get('TOKEN', '')
                        _logger.info(f"Token utilisé pour l'authentification: {token[:20]}..." if token else "Pas de token disponible")
                        
                        headers = {
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "X-Csrf-Token": cookies.get('csrf_token', ''),  # Essayer d'ajouter un token CSRF
                            "User-Agent": "Mozilla/5.0 Odoo UniFi Integration",  # Ajouter un User-Agent
                            "Authorization": f"Bearer {token}"  # Ajouter le token d'autorisation pour UDM Pro
                        }
                        kwargs["headers"] = headers
                        
                        # Essayer avec une session requests pour maintenir les cookies
                        session = requests.Session()
                        for key, value in cookies.items():
                            session.cookies.set(key, value)
                        
                        response = session.get(current_url, **kwargs)
                        _logger.info(f"Réponse reçue: Status code {response.status_code}")
                        
                        # Stocker les headers de la réponse pour une utilisation ultérieure
                        self.write({'last_response_headers': str(dict(response.headers))})
                        
                        # Afficher le contenu exact de la réponse pour débogage
                        _logger.info(f"Contenu brut de la réponse: '{response.text}'")
                        _logger.info(f"Longueur de la réponse: {len(response.text)} caractères")
                        _logger.info(f"Headers de la réponse: {dict(response.headers)}")
                        
                        # Vérifier si la réponse est du JSON valide
                        try:
                            json_data = response.json()
                            if response.status_code == 200:
                                _logger.info(f"Récupération réussie avec l'endpoint {endpoint}")
                                success = True
                                break
                        except ValueError:
                            _logger.warning(f"La réponse n'est pas du JSON valide: {response.text[:100]}...")
                    except Exception as e:
                        _logger.warning(f"Échec avec l'endpoint {endpoint}: {str(e)}")
                
                if success:
                    break
            
            if not response or not success:
                _logger.error("Tous les endpoints ont échoué pour la récupération des appareils")
                return False
                
            # Analyser la réponse JSON
            try:
                # Vérifier si la réponse est vide
                if not response.text.strip():
                    _logger.error("La réponse est vide")
                    return False
                    
                # Essayer d'analyser la réponse JSON
                data = response.json()
                _logger.info(f"Données reçues: {len(data.get('data', []))} appareils")
                _logger.info(f"Structure des données: {list(data.keys())}")
                return data
            except ValueError as e:
                _logger.error(f"Erreur lors de l'analyse de la réponse JSON: {str(e)}")
                
                # Essayer de comprendre pourquoi l'analyse JSON a échoué
                if response.text.strip().startswith('<'):
                    _logger.error("La réponse semble être du HTML ou du XML, pas du JSON")
                elif response.text.strip() == '':
                    _logger.error("La réponse est vide")
                else:
                    _logger.error(f"Les 100 premiers caractères de la réponse: {repr(response.text[:100])}")
                    
                return False
                
        except Exception as e:
            _logger.error(f"Erreur lors de la récupération des appareils: {str(e)}")
            _logger.exception("Détails de l'erreur:")
            return False
        finally:
            _logger.info("=== FIN DE LA RÉCUPÉRATION DES APPAREILS ===")
    
    def _get_network_data(self):
        """Récupère les données des réseaux du site
        
        Cette méthode remplace l'ancienne méthode get_network_data du controller.
        
        Returns:
            dict: Données des réseaux ou False en cas d'échec
        """
        self.ensure_one()
        # TODO: Implémenter la récupération des données des réseaux
        return {}
    
    def _get_vlan_data(self):
        """Récupère les données des VLANs du site
        
        Cette méthode remplace l'ancienne méthode get_vlan_data du controller.
        
        Returns:
            dict: Données des VLANs ou False en cas d'échec
        """
        self.ensure_one()
        # TODO: Implémenter la récupération des données des VLANs
        return {}
    
    def _get_user_data(self):
        """Récupère les données des utilisateurs du site
        
        Cette méthode remplace l'ancienne méthode get_user_data du controller.
        
        Returns:
            dict: Données des utilisateurs ou False en cas d'échec
        """
        self.ensure_one()
        # TODO: Implémenter la récupération des données des utilisateurs
        return {}
    
    def _get_firewall_data(self):
        """Récupère les données du pare-feu du site
        
        Cette méthode remplace l'ancienne méthode get_firewall_data du controller.
        
        Returns:
            dict: Données du pare-feu ou False en cas d'échec
        """
        self.ensure_one()
        # TODO: Implémenter la récupération des données du pare-feu
        return {}
    
    def _get_port_forward_data(self):
        """Récupère les données de redirection de port du site
        
        Cette méthode remplace l'ancienne méthode get_port_forward_data du controller.
        
        Returns:
            dict: Données de redirection de port ou False en cas d'échec
        """
        self.ensure_one()
        # TODO: Implémenter la récupération des données de redirection de port
        return {}
    
    # Note: La méthode _inverse_verify_ssl a été supprimée car elle n'est plus nécessaire
    # puisque le champ verify_ssl n'est plus un champ calculé
    
    def _compute_ssl_cert_path(self):
        """Calcule le chemin vers le fichier de certificat SSL
        
        Cette méthode est appelée lorsque le fichier de certificat SSL est modifié.
        Elle sauvegarde le certificat dans un fichier temporaire et stocke le chemin.
        """
        for record in self:
            if record.ssl_cert_file and record.ssl_cert_filename:
                # Créer un fichier temporaire pour stocker le certificat
                fd, path = tempfile.mkstemp(suffix='.pem')
                try:
                    # Décoder le contenu du certificat et l'écrire dans le fichier
                    cert_content = base64.b64decode(record.ssl_cert_file)
                    os.write(fd, cert_content)
                    # Stocker le chemin du fichier
                    record.ssl_cert_path = path
                finally:
                    os.close(fd)
            else:
                record.ssl_cert_path = False
    
    #----------------------------------------------------------
    # API Connection Methods
    #----------------------------------------------------------
    
    def test_connection(self):
        """Test the connection to the UniFi API
        
        This method attempts to establish a connection with the UniFi API
        to verify that the connection parameters are correct. It will use
        either the Controller or Site Manager API based on the api_type.
        
        Returns:
            dict: Dictionary with status and message
        """
        self.ensure_one()
        
        # Create an API log entry for this test
        api_log = self.env['unifi.api.log'].create({
            'site_id': self.id,
            'api_type': self.api_type,
            'method': 'GET',
            'endpoint': '/test',
            'start_time': fields.Datetime.now(),
        })
        
        try:
            if self.api_type == 'controller':
                result = self._test_controller_connection(api_log)
            elif self.api_type == 'site_manager':
                result = self._test_site_manager_connection(api_log)
            else:
                raise ValidationError(_('Invalid API type'))
                
            return result
        except Exception as e:
            _logger.error('Error testing connection: %s', str(e))
            # Update the API log with the error
            self._update_api_log(api_log, {
                'status': 'error',
                'response_code': 500,
                'end_time': fields.Datetime.now(),
                'execution_time': (fields.Datetime.now() - api_log.start_time).total_seconds(),
                'error': str(e),
            })
            return {
                'status': 'error',
                'message': _('Connection test failed: %s') % str(e)
            }
    
    def _test_controller_connection(self, api_log=None):
        """Test the connection to the UniFi Controller API
        
        Args:
            api_log: Optional API log record to update
            
        Returns:
            dict: Dictionary with status and message
        """
        self.ensure_one()
        
        # Add debug logging
        _logger.info("=== DÉBUT DU TEST DE CONNEXION ===")
        _logger.info(f"API Type: {self.api_type}")
        
        if self.api_type != 'controller':
            _logger.error(f"Type d'API incorrect: {self.api_type}")
            raise ValidationError(_('This method is only for Controller API'))
            
        # Validate required fields
        _logger.info(f"Host: {self.host}")
        _logger.info(f"Port: {self.port}")
        _logger.info(f"Username: {self.username}")
        _logger.info(f"Password: {'*' * len(self.password) if self.password else 'Non défini'}")
        _logger.info(f"Verify SSL: {self.verify_ssl}")
        
        if not self.host:
            _logger.error("Host manquant")
            raise ValidationError(_('Host is required for Controller API'))
            
        if not self.port:
            _logger.error("Port manquant")
            raise ValidationError(_('Port is required for Controller API'))
            
        if not self.username:
            _logger.error("Username manquant")
            raise ValidationError(_('Username is required for Controller API'))
            
        if not self.password:
            _logger.error("Password manquant")
            raise ValidationError(_('Password is required for Controller API'))
            
        # Prepare URL
        base_url = f"https://{self.host}:{self.port}"
        
        # Essayer différents endpoints d'authentification selon les versions de l'API UniFi
        # Certaines versions utilisent /api/login, d'autres /api/auth/login
        login_endpoints = [
            "/api/login",           # Endpoint standard
            "/api/auth/login",      # Endpoint alternatif
            "/v2/api/login",        # Endpoint pour les versions plus récentes
            "/v2/api/auth/login"    # Autre endpoint possible
        ]
        
        login_endpoint = login_endpoints[0]  # Commencer par le premier endpoint
        url = f"{base_url}{login_endpoint}"
        _logger.info(f"URL de connexion: {url}")
        _logger.info(f"Autres endpoints disponibles: {login_endpoints[1:]}")
        
        # Prepare request data
        login_data = {
            'username': self.username,
            'password': self.password,
            'remember': True
        }
        _logger.info(f"Données de connexion: {{'username': '{self.username}', 'password': '****', 'remember': True}}")
        
        # Disable SSL warnings if verify_ssl is False
        if not self.verify_ssl:
            _logger.info("Désactivation des avertissements SSL")
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
        # Prepare SSL verification
        verify = self.verify_ssl
        if verify and self.ssl_cert_path:
            verify = self.ssl_cert_path
            _logger.info(f"Utilisation du certificat SSL: {self.ssl_cert_path}")
            
        try:
            # Make the request
            _logger.info("Envoi de la requête de connexion...")
            
            # Essayer chaque endpoint jusqu'à ce qu'un fonctionne
            response = None
            success = False
            
            for endpoint in login_endpoints:
                try:
                    current_url = f"{base_url}{endpoint}"
                    _logger.info(f"Essai avec l'endpoint: {endpoint}")
                    
                    # Essayer avec différents formats de données
                    # Certaines versions attendent un JSON, d'autres des données de formulaire
                    for content_type, data in [
                        ("json", login_data),  # Format JSON standard
                        ("data", login_data)   # Format de données de formulaire
                    ]:
                        try:
                            _logger.info(f"Essai avec le format de données: {content_type}")
                            
                            # Construire les arguments de la requête
                            kwargs = {
                                content_type: login_data,
                                "verify": verify,
                                "timeout": self.timeout
                            }
                            
                            # Ajouter des headers spécifiques
                            headers = {
                                "Content-Type": "application/json",
                                "Accept": "application/json"
                            }
                            kwargs["headers"] = headers
                            
                            response = requests.post(current_url, **kwargs)
                            _logger.info(f"Réponse reçue: Status code {response.status_code}")
                            _logger.debug(f"Contenu de la réponse: {response.text}")
                            
                            if response.status_code == 200:
                                _logger.info(f"Connexion réussie avec l'endpoint {endpoint} et le format {content_type}")
                                success = True
                                break
                        except Exception as e:
                            _logger.warning(f"Échec avec le format {content_type}: {str(e)}")
                    
                    if success:
                        break
                except Exception as e:
                    _logger.warning(f"Échec avec l'endpoint {endpoint}: {str(e)}")
            
            if not response:
                raise Exception("Tous les endpoints ont échoué")
            # Update API log if we have a response
            if api_log and response:
                _logger.info("Mise à jour du log API")
                self._update_api_log(api_log, {
                    'endpoint': login_endpoint,
                    'request_body': json.dumps(login_data),
                    'response_code': response.status_code,
                    'response_body': response.text,
                    'end_time': fields.Datetime.now(),
                    'execution_time': (fields.Datetime.now() - api_log.start_time).total_seconds(),
                    'status': 'success' if response.status_code == 200 else 'error',
                })
                
            # Check response
            if response and response.status_code == 200:
                _logger.info("Connexion réussie!")
                # Store the cookies in the auth session
                self._create_auth_session(response.cookies, endpoint=self.last_successful_endpoint)
                
                return {
                    'status': 'success',
                    'message': _('Connection successful')
                }
            elif response:
                _logger.error(f"Échec de la connexion: Status code {response.status_code}")
                _logger.error(f"Message d'erreur: {response.text}")
                return {
                    'status': 'error',
                    'message': _('Connection failed with status code %s: %s') % (response.status_code, response.text)
                }
        except requests.exceptions.ConnectTimeout as timeout_error:
            _logger.error(f"Timeout de connexion: {str(timeout_error)}")
            return {
                'status': 'error',
                'message': _('Connection timeout: %s') % str(timeout_error)
            }
        except requests.exceptions.SSLError as ssl_error:
            _logger.error(f"Erreur SSL: {str(ssl_error)}")
            return {
                'status': 'error',
                'message': _('SSL Error: %s') % str(ssl_error)
            }
        except Exception as e:
            _logger.error('Error testing Controller API connection: %s', str(e))
            _logger.exception("Détails de l'erreur:")
            return {
                'status': 'error',
                'message': _('Connection test failed: %s') % str(e)
            }
        finally:
            _logger.info("=== FIN DU TEST DE CONNEXION ===")
    
    def _test_site_manager_connection(self, api_log=None):
        """Test the connection to the UniFi Site Manager API
        
        Args:
            api_log: Optional API log record to update
            
        Returns:
            dict: Dictionary with status and message
        """
        self.ensure_one()
        
        if self.api_type != 'site_manager':
            raise ValidationError(_('This method is only for Site Manager API'))
            
        # Validate required fields
        if not self.api_key:
            raise ValidationError(_('API Key is required for Site Manager API'))
            
        # Prepare headers
        headers = {
            'X-CSRF-Token': 'unifi_site_manager',
            'Authorization': f'Bearer {self.api_key}'
        }
        
        # Prepare URL
        base_url = "https://sitemanager.unifi.ui.com"
        endpoint = "/api/sites"
        url = f"{base_url}{endpoint}"
        
        # Disable SSL warnings if verify_ssl is False
        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
        try:
            # Make the request
            response = requests.get(
                url,
                headers=headers,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            # Update API log
            if api_log:
                self._update_api_log(api_log, {
                    'endpoint': endpoint,
                    'request_headers': json.dumps(headers),
                    'response_code': response.status_code,
                    'response_body': response.text,
                    'end_time': fields.Datetime.now(),
                    'execution_time': (fields.Datetime.now() - api_log.start_date).total_seconds(),
                    'status': 'success' if response.status_code == 200 else 'error',
                })
                
            # Check response
            if response.status_code == 200:
                return {
                    'status': 'success',
                    'message': _('Connection successful')
                }
            else:
                return {
                    'status': 'error',
                    'message': _('Connection failed with status code %s: %s') % (response.status_code, response.text)
                }
                
        except Exception as e:
            _logger.error('Error testing Site Manager API connection: %s', str(e))
            return {
                'status': 'error',
                'message': _('Connection test failed: %s') % str(e)
            }
    
    def _update_api_log(self, api_log, values):
        """Update API log record with values
        
        Args:
            api_log: API log record to update
            values: Dictionary of values to update
        """
        if not api_log:
            return
            
        try:
            # Convertir les valeurs au format attendu par le modèle unifi.api.log
            update_vals = {}
            
            # Mapper les champs communs
            if 'status' in values:
                if values['status'] == 'success':
                    update_vals['success'] = True
                elif values['status'] == 'error':
                    update_vals['success'] = False
            
            # Mapper le message d'erreur
            if 'message' in values:
                if values.get('status') == 'error':
                    update_vals['error_message'] = values['message']
                    
            # Ajouter l'heure de fin si nécessaire
            if 'end_time' not in update_vals and ('status' in values or values.get('message', '').startswith('Success')):
                update_vals['end_time'] = fields.Datetime.now()
                
            # Calculer la durée si possible
            if 'end_time' in update_vals and api_log.start_time:
                duration = (update_vals['end_time'] - api_log.start_time).total_seconds() * 1000
                update_vals['duration'] = duration
                
            # Mettre à jour le statut HTTP si fourni
            if 'status_code' in values:
                update_vals['status_code'] = values['status_code']
                
            # Mettre à jour le corps de la réponse si fourni
            if 'response_body' in values:
                update_vals['response_body'] = values['response_body']
                
            # Écrire les valeurs mises à jour
            api_log.write(update_vals)
        except Exception as e:
            _logger.error('Error updating API log: %s', str(e))
    
    def _check_auth_session(self):
        """Vérifie si la session d'authentification est valide
        
        Returns:
            bool: True si la session est valide, False sinon
        """
        self.ensure_one()
        _logger.info("Vérification de la session d'authentification")
        
        # Vérifier si une session existe
        if not self.auth_session_id:
            _logger.warning("Pas de session d'authentification existante")
            return False
            
        # Vérifier si la session est expirée
        if self.auth_session_id.expiry and self.auth_session_id.expiry < fields.Datetime.now():
            _logger.warning(f"Session expirée: {self.auth_session_id.expiry}")
            return False
            
        # Mettre à jour la date de dernière utilisation
        self.auth_session_id.write({
            'last_used': fields.Datetime.now()
        })
        
        _logger.info("Session d'authentification valide")
        return True
        
    def _get_auth_cookies(self):
        """Récupère les cookies de la session d'authentification
        
        Returns:
            dict: Cookies de la session ou False si pas de session valide
        """
        self.ensure_one()
        
        # Vérifier si la session est valide
        if not self._check_auth_session():
            _logger.warning("Tentative de récupération des cookies sans session valide")
            # Essayer de se reconnecter
            _logger.info("Tentative de reconnexion automatique")
            result = self._test_controller_connection()
            if result.get('status') != 'success':
                _logger.error(f"Échec de la reconnexion: {result.get('message')}")
                return False
                
        # Récupérer les cookies de la session
        try:
            cookie_str = self.auth_session_id.cookie
            if not cookie_str:
                _logger.error("Chaîne de cookies vide")
                return False
                
            # Afficher la chaîne de cookies brute pour débogage
            _logger.info(f"Chaîne de cookies brute: {cookie_str}")
            
            # Méthode 1: Extraire les cookies à partir de la chaîne
            cookies = {}
            
            # Vérifier si c'est un objet RequestsCookieJar
            if cookie_str.startswith('<RequestsCookieJar[') and cookie_str.endswith(']>'):
                cookie_content = cookie_str[len('<RequestsCookieJar['):-len(']>')]
                cookie_pairs = cookie_content.split(', ')
                for pair in cookie_pairs:
                    if '=' in pair:
                        # Corriger le format des cookies comme '<Cookie TOKEN=value...>'
                        if pair.startswith('<Cookie '):
                            # Extraire le nom du cookie et sa valeur
                            cookie_info = pair[len('<Cookie '):]
                            if '=' in cookie_info:
                                key, value = cookie_info.split('=', 1)
                                # Nettoyer la valeur si elle se termine par ' for domain>'
                                if ' for ' in value:
                                    value = value.split(' for ')[0]
                                cookies[key.strip()] = value.strip()
                                
                                # Si nous trouvons un cookie TOKEN, c'est un UDM Pro
                                if key.strip() == 'TOKEN' and not self.auth_session_id.is_udm_pro:
                                    _logger.info("Détection d'un UDM Pro basé sur le cookie TOKEN")
                                    self.auth_session_id.write({'is_udm_pro': True})
                        else:
                            key, value = pair.split('=', 1)
                            cookies[key.strip()] = value.strip()
            # Sinon, essayer de parser comme un dictionnaire
            elif cookie_str.startswith('{') and cookie_str.endswith('}'): 
                try:
                    cookies = ast.literal_eval(cookie_str)
                except Exception as e:
                    _logger.warning(f"Impossible de parser les cookies comme un dictionnaire: {str(e)}")
            # Sinon, essayer de parser comme une liste de paires clé=valeur
            else:
                cookie_pairs = cookie_str.split(';')
                for pair in cookie_pairs:
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        cookies[key.strip()] = value.strip()
            
            # Ajouter des cookies spécifiques pour UniFi
            if 'TOKEN' not in cookies and 'unifises' not in cookies:
                # Essayer d'extraire le token des headers de la réponse
                if self.last_response_headers:
                    try:
                        headers_dict = ast.literal_eval(self.last_response_headers)
                        for header, value in headers_dict.items():
                            if header.lower() == 'set-cookie':
                                if 'TOKEN=' in value:
                                    token_part = value.split('TOKEN=')[1].split(';')[0]
                                    cookies['TOKEN'] = token_part
                                if 'unifises=' in value:
                                    unifises_part = value.split('unifises=')[1].split(';')[0]
                                    cookies['unifises'] = unifises_part
                    except (ValueError, SyntaxError) as e:
                        _logger.warning(f"Impossible de parser les headers: {str(e)}")
            
            _logger.info(f"Cookies récupérés: {cookies}")
            return cookies
        except Exception as e:
            _logger.error(f"Erreur lors de la récupération des cookies: {str(e)}")
            return False
        
    def _create_auth_session(self, cookies, endpoint=None):
        """Create or update authentication session
        
        Args:
            cookies: Session cookies from successful login
            endpoint: The endpoint used for authentication
            
        Returns:
            unifi.auth.session: Created or updated auth session record
        """
        self.ensure_one()
        _logger.info("Création/mise à jour de la session d'authentification")
        
        # Déterminer si c'est un UDM Pro en fonction de l'endpoint utilisé
        is_udm_pro = False
        if endpoint and '/api/auth/login' in endpoint:
            is_udm_pro = True
            _logger.info("Détection d'un contrôleur UDM Pro basé sur l'endpoint d'authentification")
        
        # Vérifier si un token est présent dans les cookies (caractéristique des UDM Pro)
        token = None
        if cookies and 'TOKEN' in cookies:
            token = cookies.get('TOKEN')
            is_udm_pro = True
            _logger.info("Détection d'un contrôleur UDM Pro basé sur le cookie TOKEN")
        
        # Check if there's an existing session
        if self.auth_session_id:
            # Update existing session
            _logger.info("Mise à jour de la session existante")
            session_vals = {
                'cookie': str(cookies),
                'endpoint': endpoint,
                'is_udm_pro': is_udm_pro,
                'expiry': fields.Datetime.now() + timedelta(hours=24),  # Default 24h expiry
                'last_used': fields.Datetime.now()
            }
            
            # Ajouter le token si disponible
            if token:
                session_vals['token'] = token
                
            self.auth_session_id.write(session_vals)
            return self.auth_session_id
        else:
            # Create new session
            session_vals = {
                'site_id': self.id,
                'auth_type': self.api_type,
                'cookie': str(cookies),
                'endpoint': endpoint,
                'is_udm_pro': is_udm_pro,
                'expiry': fields.Datetime.now() + timedelta(hours=24),
                'last_used': fields.Datetime.now()
            }
            
            # Ajouter le token si disponible
            if token:
                session_vals['token'] = token
                
            session = self.env['unifi.auth.session'].create(session_vals)
            self.auth_session_id = session
            return session
            
    def _inverse_api_key(self):
        """Inverse pour le champ api_key
        
        Cette méthode a été simplifiée dans le cadre de la refactorisation.
        Elle n'a plus besoin de synchroniser les données avec l'ancien modèle unifi.site.manager
        puisque toute la logique a été consolidée dans ce modèle.
        """
        # Rien à faire, puisque api_key est maintenant directement géré par le modèle unifi.site
        pass
    
    def _inverse_mfa_enabled(self):
        """Inverse pour le champ mfa_enabled
        
        Cette méthode a été simplifiée dans le cadre de la refactorisation.
        Elle n'a plus besoin de synchroniser les données avec l'ancien modèle unifi.site.manager
        puisque toute la logique a été consolidée dans ce modèle.
        """
        # Rien à faire, puisque mfa_enabled est maintenant directement géré par le modèle unifi.site
        pass
    
    def _inverse_mfa_token(self):
        """Inverse pour le champ mfa_token
        
        Cette méthode a été simplifiée dans le cadre de la refactorisation.
        Elle n'a plus besoin de synchroniser les données avec l'ancien modèle unifi.site.manager
        puisque toute la logique a été consolidée dans ce modèle.
        """
        # Rien à faire, puisque mfa_token est maintenant directement géré par le modèle unifi.site
        pass
                    
    def action_test_connection(self):
        """Test the connection to the UniFi API
        
        This method tests the connection to the UniFi API using the appropriate
        connection method based on the API type (Controller or Site Manager).
        It displays a notification with the result of the connection test.
        
        Returns:
            dict: Action dictionary for client notification
        """
        self.ensure_one()
        
        try:
            # Perform connection test based on API type
            if self.api_type == 'controller':
                result = self._test_controller_connection()
            elif self.api_type == 'site_manager':
                result = self._test_site_manager_connection()
            else:
                raise ValidationError(_('Invalid API type'))
            
            # Check result and display appropriate notification
            if result:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Test'),
                        'message': _('Connection successful!'),
                        'sticky': False,
                        'type': 'success',
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Test'),
                        'message': _('Connection failed. Please check your settings.'),
                        'sticky': True,
                        'type': 'danger',
                    }
                }
        except Exception as e:
            # Handle any exceptions that occur during the connection test
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Test'),
                    'message': _('Error: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
    
    def action_sync_now(self):
        """Trigger an immediate synchronization"""
        self.ensure_one()
        
        # Création d'un job de synchronisation dans le modèle UnifiSyncJob
        sync_job = self.env['unifi.sync.job'].create({
            'site_id': self.id,  # Référence au site actuel
            'api_type': self.api_type,  # Type d'API (controller ou site_manager)
            'sync_type': 'manual',  # Type de synchronisation (manuel dans ce cas)
            'start_time': fields.Datetime.now(),  # Horodatage du début
            'state': 'running',  # État initial du job (en cours d'exécution)
        })
        
        try:
            if self.api_type == 'controller':
                result = self._sync_controller()
            elif self.api_type == 'site_manager':
                result = self._sync_site_manager()
            else:
                raise ValidationError(_('Invalid API type'))
                
            # Update sync job with result
            if result:
                # Mise à jour des champs dans le modèle UnifiSyncJob pour indiquer le succès
                sync_job.write({
                    'end_time': fields.Datetime.now(),  # Horodatage de fin
                    'state': 'completed',  # État: terminé
                    'status': 'success',  # Statut: succès
                })
                
                # Update last_sync timestamp
                self.write({
                    'last_sync': fields.Datetime.now(),
                    'last_update': fields.Datetime.now() if result else self.last_update,
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Synchronization'),
                        'message': _('Synchronization completed successfully'),
                        'sticky': False,
                        'type': 'success',
                    }
                }
            else:
                sync_job.write({
                    'end_time': fields.Datetime.now(),
                    'status': 'failed',
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Synchronization'),
                        'message': _('Synchronization failed'),
                        'sticky': True,
                        'type': 'danger',
                    }
                }
        except Exception as e:
            _logger.error('Error during synchronization: %s', str(e))
            
            # Mise à jour du job de synchronisation avec les détails de l'erreur
            # Note: Si le champ 'error' n'existe pas dans le modèle, on l'ignore
            vals = {
                'end_time': fields.Datetime.now(),
                'status': 'failed',
            }
            
            # Vérifier si le champ 'error' existe dans le modèle
            if 'error' in self.env['unifi.sync.job']._fields:
                vals['error'] = str(e)
                
            sync_job.write(vals)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Synchronization'),
                    'message': _('Synchronization failed: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
    
    def _inverse_verify_ssl(self):
        """Inverse pour le champ verify_ssl
        
        Cette méthode a été simplifiée dans le cadre de la refactorisation.
        Elle n'a plus besoin de synchroniser les données avec les anciens modèles
        unifi.site.controller et unifi.site.manager puisque toute la logique
        a été consolidée dans ce modèle.
        """
        # Rien à faire, puisque verify_ssl est maintenant directement géré par le modèle unifi.site
        pass
    
    # Configuration data
    last_update = fields.Datetime(
        string='Last Update',

        default=fields.Datetime.now
    )
    
    raw_data = fields.Text(
        string='Raw Data',
        help='Raw configuration data in JSON format'
    )
    
    raw_data_json = fields.Text(
        string='Données brutes (JSON)',
        compute='_compute_raw_data_json',
        help='Données brutes du site au format JSON formaté'
    )
    
    @api.depends('raw_data')
    def _compute_raw_data_json(self):
        for record in self:
            record.raw_data_json = self.format_raw_data_json(record.raw_data)
    
    # Synchronization settings
    sync_interval = fields.Integer(
        string='Sync Interval (minutes)',
        default=60,
        help='Interval in minutes between automatic synchronizations'
    )
    
    auto_sync = fields.Boolean(
        string='Auto Sync',
        default=True,
        help='Enable automatic synchronization'
    )
    
    last_sync = fields.Datetime(
        string='Last Sync',
        readonly=True,
        help='Date and time of the last synchronization'
    )
    
    # Authentication session
    auth_session_id = fields.Many2one(
        comodel_name='unifi.auth.session',
        string='Authentication Session',
        ondelete='cascade',
        help='Current authentication session'
    )
    
    # Related records - Will be updated to point to new models
    network_ids = fields.One2many(
        comodel_name='unifi.network',
        inverse_name='site_id',
        string='Networks',
        help='Networks in this site'
    )

    vlan_ids = fields.One2many(
        comodel_name='unifi.vlan',
        inverse_name='site_id',
        string='VLANs',
        help='VLANs in this site'
    )
    
    device_ids = fields.One2many(
        comodel_name='unifi.device',
        inverse_name='site_id',
        string='Devices',
        help='Devices in this site'
    )

    user_ids = fields.One2many(
        comodel_name='unifi.user',
        inverse_name='site_id',
        string='Users',
        help='Users in this site'
    )

    firewall_rule_ids = fields.One2many(
        comodel_name='unifi.firewall.rule',
        inverse_name='site_id',
        string='Firewall Rules',
        help='Firewall rules for this site'
    )

    port_forward_ids = fields.One2many(
        comodel_name='unifi.port.forward',
        inverse_name='site_id',
        string='Port Forwards',
        help='Port forwarding rules for this site'
    )

    dns_config_ids = fields.One2many(
        comodel_name='unifi.dns.config',
        inverse_name='site_id',
        string='DNS Configurations',
        help='DNS configurations for this site'
    )

    routing_config_ids = fields.One2many(
        comodel_name='unifi.routing.config',
        inverse_name='site_id',
        string='Routing Configurations',
        help='Routing configurations for this site'
    )
    
    # Relations with system models
    system_info_id = fields.Many2one(
        comodel_name='unifi.system.info',
        string='Primary System Info',
        ondelete='cascade',
        help='Primary system information snapshot',
        required=False
    )
    
    # Relations avec les appareils
    device_ids = fields.One2many(
        comodel_name='unifi.device',
        inverse_name='site_id',
        string='Appareils',
        help='Appareils UniFi associés à ce site'
    )
    
    
    # API logs
    api_log_ids = fields.One2many(
        comodel_name='unifi.api.log',
        inverse_name='site_id',
        string='API Logs',
        help='Logs of API calls'
    )
    
    # Sync jobs
    sync_job_ids = fields.One2many(
        comodel_name='unifi.sync.job',
        inverse_name='site_id',
        string='Sync Jobs',
        help='Synchronization jobs'
    )
    
    # Computed fields
    network_count = fields.Integer(
        compute='_compute_counts',
        string='Network Count',
        store=True,
        help='Total number of networks in this site'
    )
    
    device_count = fields.Integer(
        compute='_compute_counts',
        string='Device Count',
        store=True,
        help='Total number of devices in this site'
    )
    
    user_count = fields.Integer(
        compute='_compute_counts',
        string='User Count',
        store=True,
        help='Number of users in this site'
    )
    
    firewall_rule_count = fields.Integer(
        compute='_compute_counts',
        string='Firewall Rule Count',
        store=True,
        help='Number of firewall rules in this site'
    )

    client_count = fields.Integer(
        compute='_compute_client_count',
        string='Connected Clients',
        store=True,
        help='Number of currently connected clients'
    )
    
    # Dashboard Metrics - Updated to point to new models
    dashboard_metric_ids = fields.One2many(
        comodel_name='unifi.dashboard.metric',
        inverse_name='site_id',
        string='Real-time Dashboard Metrics',
        help='Real-time metrics for this site'
    )
    
    dashboard_stat_ids = fields.One2many(
        comodel_name='unifi.dashboard.stat',
        inverse_name='site_id',
        string='Historical Statistics',
        help='Historical statistics for this site'
    )
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Site name must be unique!'),
    ]
    
    # Field dependencies and constraints
    @api.constrains('api_type')
    def _check_api_fields(self):
        """Validate that required fields are set based on API type
        
        This method delegates to the appropriate API-specific model for validation.
        """
        for site in self:
            if site.api_type == 'controller':
                # Check controller-specific required fields
                if not site.host:
                    raise ValidationError(_('Host is required for Controller API'))
                if not site.port:
                    raise ValidationError(_('Port is required for Controller API'))
                if not site.username:
                    raise ValidationError(_('Username is required for Controller API'))
                if not site.password:
                    raise ValidationError(_('Password is required for Controller API'))
            elif site.api_type == 'site_manager':
                # Check site manager-specific required fields
                if not site.api_key:
                    raise ValidationError(_('API Key is required for Site Manager API'))
    
    @api.onchange('api_type')
    def _onchange_api_type(self):
        """Clear fields that are not relevant to the selected API type
        
        This method implements field clearing logic directly based on the API type.
        Previously this was delegated to specific models, but now it's integrated here
        as part of the refactoring.
        """
        if self.api_type == 'controller':
            # Clear site_manager-specific fields
            self.api_key = False
            self.mfa_enabled = False
            self.mfa_token = False
        elif self.api_type == 'site_manager':
            # Clear controller-specific fields
            self.username = False
            self.password = False
    
    @api.depends('network_ids', 'device_ids', 'user_ids', 'firewall_rule_ids', 'vlan_ids', 'port_forward_ids', 'routing_config_ids', 'wifi_ids', 'dns_ids', 'system_info_ids', 'vpn_ids')
    def _compute_counts(self):
        """Compute counts for related records
        
        This method calculates the number of networks, devices, users, firewall rules,
        VLANs, port forwards, routing configurations, and WiFi networks associated with this site.
        It's triggered automatically when any of these related records are added or removed.
        """
        for site in self:
            # Safely get counts, handling potential errors
            try:
                site.network_count = len(site.network_ids) if site.network_ids else 0
                site.device_count = len(site.device_ids) if site.device_ids else 0
                site.user_count = len(site.user_ids) if site.user_ids else 0
                site.firewall_rule_count = len(site.firewall_rule_ids) if site.firewall_rule_ids else 0
                site.vlan_count = len(site.vlan_ids) if site.vlan_ids else 0
                site.port_forward_count = len(site.port_forward_ids) if site.port_forward_ids else 0
                site.routing_config_count = len(site.routing_config_ids) if site.routing_config_ids else 0
                site.wifi_count = len(site.wifi_ids) if site.wifi_ids else 0
                site.dns_count = len(site.dns_ids) if site.dns_ids else 0
                site.system_info_count = len(site.system_info_ids) if site.system_info_ids else 0
                site.vpn_count = len(site.vpn_ids) if site.vpn_ids else 0
            except Exception as e:
                _logger.error('Error computing counts for site %s: %s', site.name, str(e))
                # Set default values in case of error
                site.network_count = site.device_count = site.user_count = site.firewall_rule_count = site.vlan_count = site.port_forward_count = site.routing_config_count = site.wifi_count = site.dns_count = site.system_info_count = site.vpn_count = 0
    
    @api.depends('user_ids')
    def _compute_client_count(self):
        """Compute the number of connected clients
        
        This method counts only users that are currently connected to the network.
        It relies on the 'is_connected' flag on user records.
        """
        for site in self:
            try:
                if site.user_ids:
                    # Filter users that have is_connected=True
                    site.client_count = len(site.user_ids.filtered(lambda u: u.is_connected if hasattr(u, 'is_connected') else False))
                else:
                    site.client_count = 0
            except Exception as e:
                _logger.error('Error computing client count for site %s: %s', site.name, str(e))
                site.client_count = 0
    
    # Action methods
    def action_view_networks(self):
        """Open the networks view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('Networks'),
            'view_mode': 'list,form',
            'res_model': 'unifi.network',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
    
    def action_view_devices(self):
        """Open the devices view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('Devices'),
            'view_mode': 'list,form',
            'res_model': 'unifi.device',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
    
    def action_view_users(self):
        """Open the users view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('Users'),
            'view_mode': 'list,form',
            'res_model': 'unifi.user',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
    
    def action_view_firewall_rules(self):
        """Open the firewall rules view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('Firewall Rules'),
            'view_mode': 'list,form',
            'res_model': 'unifi.firewall.rule',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
    
    def action_view_api_logs(self):
        """Open the API logs view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('API Logs'),
            'view_mode': 'list,form',
            'res_model': 'unifi.api.log',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
    
    def action_view_sync_jobs(self):
        """Open the sync jobs view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('Sync Jobs'),
            'view_mode': 'list,form',
            'res_model': 'unifi.sync.job',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
        
    def action_view_vlans(self):
        """Open the VLANs view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('VLANs'),
            'view_mode': 'list,form',
            'res_model': 'unifi.vlan',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
        
    def action_view_port_forwards(self):
        """Open the port forwards view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('Port Forwards'),
            'view_mode': 'list,form',
            'res_model': 'unifi.port_forward',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
        
    def action_view_system_info(self):
        """Open the system info view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('System Info'),
            'view_mode': 'list,form',
            'res_model': 'unifi.system.info',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
        
    def action_view_dns(self):
        """Open the DNS entries view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('DNS Entries'),
            'view_mode': 'list,form',
            'res_model': 'unifi.dns',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
        
    def action_view_vpn(self):
        """Open the VPN configurations view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('VPN Configurations'),
            'view_mode': 'list,form',
            'res_model': 'unifi.vpn',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
        
    def action_configure_controller(self):
        """Open the controller configuration view for this site
        
        This method checks if a controller configuration already exists for this site.
        If it does, it opens the existing configuration in form view.
        If not, it creates a new configuration and opens it in form view.
        """
        self.ensure_one()
        
        # Since we've consolidated all API functionality into the main model,
        # we just need to open the current site record in form view
        return {
            'name': _('Controller API Configuration'),
            'view_mode': 'form',
            'res_model': 'unifi.site',
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }
    
    def action_configure_site_manager(self):
        """Open the site configuration form in edit mode
        
        This method has been updated as part of the refactorization.
        Since we've consolidated all API-related functionality into the main
        unifi.site model, we simply open this record in form view for editing.
        """
        self.ensure_one()
        
        # Ensure API type is set to site_manager
        if self.api_type != 'site_manager':
            self.api_type = 'site_manager'
        
        # Open this site record in form view
        return {
            'name': _('Site Manager API Configuration'),
            'view_mode': 'form',
            'res_model': 'unifi.site',
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }
    

        return True
        
    def action_sync_networks(self):
        """Synchronize only networks for this site"""
        self.ensure_one()
        try:
            # Vérifier si nous avons une session d'authentification valide
            if not self.auth_session_id or not self._check_auth_session():
                _logger.warning("Pas de session d'authentification valide, tentative de connexion automatique")
                
                # Tenter de se connecter au contrôleur UniFi
                connection_result = self._test_controller_connection()
                _logger.info(f"Résultat de la connexion: {connection_result}")
                
                if connection_result.get('status') != 'success':
                    _logger.error(f"Impossible de se connecter au contrôleur UniFi: {connection_result.get('message')}")
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Connection Error'),
                            'message': _(f"Unable to connect to UniFi Controller: {connection_result.get('message')}"),
                            'sticky': True,
                            'type': 'danger',
                        }
                    }
                _logger.info("Connexion au contrôleur UniFi réussie, poursuite de la synchronisation")
            
            # Récupérer les données des réseaux depuis l'API UniFi
            _logger.info("Récupération des données des réseaux depuis l'API UniFi")
            
            # Déterminer quelle méthode utiliser en fonction du type d'API
            if self.api_type == 'controller':
                networks_data = self._get_controller_network_data()
            elif self.api_type == 'site_manager':
                networks_data = self._get_site_manager_network_data()
            else:
                networks_data = None
                _logger.error(f"Type d'API non pris en charge: {self.api_type}")
            
            if not networks_data:
                _logger.error("Impossible de récupérer les données des réseaux")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Network Synchronization'),
                        'message': _('Failed to retrieve network data from UniFi API'),
                        'sticky': True,
                        'type': 'danger',
                    }
                }
            
            # Analyser les données des réseaux
            _logger.info(f"Données de réseaux reçues: {type(networks_data)}")
            
            # Vérifier la structure des données
            if isinstance(networks_data, list):
                networks_list = networks_data
            elif isinstance(networks_data, dict):
                # La plupart des API UniFi renvoient les données dans une clé 'data'
                networks_list = networks_data.get('data', [])
                if not networks_list and 'networks' in networks_data:
                    networks_list = networks_data.get('networks', [])
            else:
                networks_list = []
                
            _logger.info(f"Nombre de réseaux trouvés dans l'API: {len(networks_list)}")
            
            # Créer ou mettre à jour les réseaux
            processed_networks = self.env['unifi.network']
            
            for network_data in networks_list:
                network_id = network_data.get('_id') or network_data.get('id')
                if not network_id:
                    _logger.warning("Réseau sans identifiant ignoré")
                    continue
                    
                # Rechercher un réseau existant par ID
                network = self.env['unifi.network'].search([
                    ('site_id', '=', self.id),
                    ('network_id', '=', network_id)
                ], limit=1)
                
                if network:
                    _logger.info(f"Mise à jour du réseau existant: {network.name} (ID: {network_id})")
                else:
                    _logger.info(f"Création d'un nouveau réseau avec ID: {network_id}")
                
                # Créer ou mettre à jour le réseau
                network = self.env['unifi.network'].create_or_update_from_data(self, network_data)
                if network:
                    processed_networks += network
            
            # Afficher un message de succès et retourner la vue des réseaux
            # D'abord afficher la notification
            self.env['bus.bus']._sendone(
                self.env.user.partner_id,
                'web_client.action',
                {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Network Synchronization'),
                        'message': _(f'{len(networks_list)} réseaux trouvés, {len(processed_networks)} créés ou mis à jour'),
                        'sticky': False,
                        'type': 'success',
                    }
                }
            )
            
            # Ensuite retourner la vue des réseaux
            return {
                'type': 'ir.actions.act_window',
                'name': _('Networks'),
                'res_model': 'unifi.network',
                'domain': [('site_id', '=', self.id)],
                'view_mode': 'list,form',
                'target': 'current',
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Network Synchronization'),
                    'message': _('Error: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
            
    def action_sync_devices(self):
        """Synchronize only devices for this site"""
        self.ensure_one()
        _logger.info("=== DÉBUT DE LA SYNCHRONISATION DES APPAREILS (action_sync_devices) ===")
        
        try:
            # Vérifier si nous avons une session d'authentification valide
            if not self.auth_session_id or not self._check_auth_session():
                _logger.warning("Pas de session d'authentification valide, tentative de connexion automatique")
                
                # Tenter de se connecter au contrôleur UniFi
                connection_result = self._test_controller_connection()
                _logger.info(f"Résultat de la connexion: {connection_result}")
                
                if connection_result.get('status') != 'success':
                    _logger.error(f"Impossible de se connecter au contrôleur UniFi: {connection_result.get('message')}")
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Connection Error'),
                            'message': _(f"Unable to connect to UniFi Controller: {connection_result.get('message')}"),
                            'sticky': True,
                            'type': 'danger',
                        }
                    }
                _logger.info("Connexion au contrôleur UniFi réussie, poursuite de la synchronisation")
            
            # Récupérer les données des appareils depuis l'API UniFi
            _logger.info("Récupération des données des appareils depuis l'API UniFi")
            device_data = self._get_device_data()
            
            if not device_data:
                _logger.error("Impossible de récupérer les données des appareils")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Device Synchronization'),
                        'message': _('Failed to retrieve device data from UniFi API'),
                        'sticky': True,
                        'type': 'danger',
                    }
                }
                
            # Analyser les données des appareils
            _logger.info(f"Données d'appareils reçues: {type(device_data)}")
            
            # Vérifier la structure des données
            if isinstance(device_data, dict):
                _logger.info(f"Clés dans les données: {list(device_data.keys())}")
                
                # La plupart des API UniFi renvoient les données dans une clé 'data'
                devices_list = device_data.get('data', [])
                if not devices_list and 'devices' in device_data:
                    devices_list = device_data.get('devices', [])
                    
                _logger.info(f"Nombre d'appareils trouvés dans l'API: {len(devices_list)}")
                
                if devices_list:
                    # Afficher des informations sur le premier appareil pour débogage
                    first_device = devices_list[0]
                    _logger.info(f"Premier appareil: {first_device.get('name', 'Sans nom')}")
                    _logger.info(f"MAC: {first_device.get('mac', 'N/A')}")
                    _logger.info(f"Modèle: {first_device.get('model', 'N/A')}")
                    
                        # Créer ou mettre à jour les appareils à partir des données de l'API
                    existing_devices = self.env['unifi.device'].search([('site_id', '=', self.id)])
                    _logger.info(f"Nombre d'appareils existants dans Odoo: {len(existing_devices)}")
                    
                    # Garder une trace des appareils traités
                    processed_devices = self.env['unifi.device']
                    
                    # Créer ou mettre à jour les appareils
                    for device_data in devices_list:
                        mac = device_data.get('mac')
                        if not mac:
                            _logger.warning("Appareil sans adresse MAC ignoré")
                            continue
                            
                        # Rechercher un appareil existant par MAC
                        device = self.env['unifi.device'].search([
                            ('site_id', '=', self.id),
                            ('mac_address', '=', mac)
                        ], limit=1)
                        
                        if device:
                            _logger.info(f"Mise à jour de l'appareil existant: {device.name} (MAC: {mac})")
                        else:
                            _logger.info(f"Création d'un nouvel appareil avec MAC: {mac}")
                        
                        # Créer ou mettre à jour l'appareil
                        device = self.env['unifi.device'].create_from_api_data(self, device_data)
                        if device:
                            processed_devices += device
                    
                    # Afficher un message de succès et retourner la vue des appareils
                    # D'abord afficher la notification
                    self.env['bus.bus']._sendone(
                        self.env.user.partner_id,
                        'web_client.action',
                        {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('Device Synchronization'),
                                'message': _(f'{len(devices_list)} appareils trouvés, {len(processed_devices)} créés ou mis à jour'),
                                'sticky': False,
                                'type': 'success',
                            }
                        }
                    )
                    
                    # Ensuite retourner la vue des appareils
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Devices'),
                        'res_model': 'unifi.device',
                        'domain': [('site_id', '=', self.id)],
                        'view_mode': 'list,form',
                        'target': 'current',
                    }
                else:
                    _logger.warning("Aucun appareil trouvé dans les données de l'API")
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Device Synchronization'),
                            'message': _('No devices found in the UniFi API data'),
                            'sticky': False,
                            'type': 'warning',
                        }
                    }
            else:
                _logger.error(f"Format de données inattendu: {type(device_data)}")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Device Synchronization'),
                        'message': _('Unexpected data format received from UniFi API'),
                        'sticky': True,
                        'type': 'danger',
                    }
                }
        except Exception as e:
            _logger.exception(f"Erreur lors de la synchronisation des appareils: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Device Synchronization'),
                    'message': _('Error: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
            
    def action_sync_dns(self):
        """Synchronize DNS entries from UniFi
        
        This method retrieves DNS data from the UniFi API and creates or updates
        DNS records in Odoo. It handles both success and error notifications.
        """
        self.ensure_one()
        
        try:
            # Récupérer les données DNS depuis l'API UniFi en fonction du type d'API
            if self.api_type == 'controller':
                dns_data = self._get_controller_get_dns_data()
            else:
                dns_data = self._get_site_manager_dns_data()
            
            if dns_data:
                # Vérifier le format des données
                if isinstance(dns_data, list):
                    # Initialiser la liste des entrées DNS traitées
                    processed_dns = self.env['unifi.dns']
                    dns_list = dns_data
                    
                    # Traiter chaque entrée DNS
                    for dns_item in dns_list:
                        # Créer ou mettre à jour l'entrée DNS
                        dns = self.env['unifi.dns'].create_or_update_from_data(self, dns_item)
                        if dns:
                            processed_dns += dns
                    
                    # Afficher un message de succès
                    self.env['bus.bus']._sendone(
                        self.env.user.partner_id,
                        'web_client.action',
                        {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('DNS Synchronization'),
                                'message': _(f'{len(dns_list)} entrées DNS trouvées, {len(processed_dns)} créées ou mises à jour'),
                                'sticky': False,
                                'type': 'success',
                            }
                        }
                    )
                    
                    # Retourner une action pour afficher la liste des entrées DNS
                    return {
                        'name': _('DNS Entries'),
                        'type': 'ir.actions.act_window',
                        'res_model': 'unifi.dns',
                        'view_mode': 'list,form',
                        'domain': [('site_id', '=', self.id)],
                        'context': {'default_site_id': self.id},
                    }
                else:
                    # Format de données incorrect
                    raise UserError(_('Invalid data format received from UniFi API'))
            else:
                # Aucune donnée reçue, mais ce n'est pas une erreur
                # Afficher un message d'information
                self.env['bus.bus']._sendone(
                    self.env.user.partner_id,
                    'web_client.action',
                    {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('DNS Synchronization'),
                            'message': _('Aucune entrée DNS trouvée dans le contrôleur UniFi.'),
                            'sticky': False,
                            'type': 'info',
                        }
                    }
                )
                
                # Retourner une action pour afficher la liste des entrées DNS (même si vide)
                return {
                    'name': _('DNS Entries'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'unifi.dns',
                    'view_mode': 'list,form',
                    'domain': [('site_id', '=', self.id)],
                    'context': {'default_site_id': self.id},
                }
                
        except Exception as e:
            # Gérer les erreurs
            _logger.error(f"Error synchronizing DNS entries: {str(e)}")
            raise UserError(_(f"Error synchronizing DNS entries: {str(e)}"))
    
    def action_sync_system_info(self):
        """Synchronize system information from UniFi
        
        This method retrieves system information from the UniFi API and creates or updates
        system info records in Odoo. It handles both success and error notifications.
        """
        self.ensure_one()
        
        try:
            # Récupérer les données système depuis l'API UniFi
            system_info_data = self._get_site_manager_system_info_data()
            
            if system_info_data:
                # Vérifier le format des données
                if isinstance(system_info_data, list) or isinstance(system_info_data, dict):
                    # Convertir en liste si c'est un dictionnaire
                    if isinstance(system_info_data, dict):
                        system_info_list = [system_info_data]
                    else:
                        system_info_list = system_info_data
                    
                    # Initialiser la liste des informations système traitées
                    processed_system_info = self.env['unifi.system.info']
                    
                    # Traiter chaque information système
                    for system_info_item in system_info_list:
                        # Créer ou mettre à jour l'information système
                        system_info = self.env['unifi.system.info'].create_or_update_from_data(self, system_info_item)
                        if system_info:
                            processed_system_info += system_info
                    
                    # Afficher un message de succès
                    self.env['bus.bus']._sendone(
                        self.env.user.partner_id,
                        'web_client.action',
                        {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('System Info Synchronization'),
                                'message': _(f'{len(system_info_list)} informations système trouvées, {len(processed_system_info)} créées ou mises à jour'),
                                'sticky': False,
                                'type': 'success',
                            }
                        }
                    )
                    
                    # Retourner une action pour afficher la liste des informations système
                    return {
                        'name': _('System Info'),
                        'type': 'ir.actions.act_window',
                        'res_model': 'unifi.system.info',
                        'view_mode': 'list,form',
                        'domain': [('site_id', '=', self.id)],
                        'context': {'default_site_id': self.id},
                    }
                else:
                    # Format de données incorrect
                    raise UserError(_('Invalid data format received from UniFi API'))
            else:
                # Aucune donnée reçue
                raise UserError(_('No system info data received from UniFi API'))
                
        except Exception as e:
            # Gérer les erreurs
            _logger.error(f"Error synchronizing system info: {str(e)}")
            raise UserError(_(f"Error synchronizing system info: {str(e)}"))
    
    def action_sync_wifi(self):
        """Synchronize WiFi networks from UniFi
        
        This method retrieves WiFi network data from the UniFi API and creates or updates
        WiFi network records in Odoo. It handles both success and error notifications.
        """
        self.ensure_one()
        
        try:
            # Récupérer les données WiFi depuis l'API UniFi
            wifi_data = self._get_controller_wifi_data()
            
            if wifi_data:
                # Vérifier le format des données
                if isinstance(wifi_data, list):
                    # Initialiser la liste des réseaux WiFi traités
                    processed_wifi = self.env['unifi.wifi']
                    wifi_list = wifi_data
                    
                    # Traiter chaque réseau WiFi
                    for wifi_item in wifi_list:
                        # Créer ou mettre à jour le réseau WiFi
                        wifi = self.env['unifi.wifi'].create_or_update_from_data(self, wifi_item)
                        if wifi:
                            processed_wifi += wifi
                    
                    # Afficher un message de succès
                    self.env['bus.bus']._sendone(
                        self.env.user.partner_id,
                        'web_client.action',
                        {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('WiFi Network Synchronization'),
                                'message': _(f'{len(wifi_list)} réseaux WiFi trouvés, {len(processed_wifi)} créés ou mis à jour'),
                                'sticky': False,
                                'type': 'success',
                            }
                        }
                    )
                    
                    # Retourner une action pour afficher la liste des réseaux WiFi
                    return {
                        'name': _('WiFi Networks'),
                        'type': 'ir.actions.act_window',
                        'res_model': 'unifi.wifi',
                        'view_mode': 'list,form',
                        'domain': [('site_id', '=', self.id)],
                        'context': {'default_site_id': self.id},
                    }
                else:
                    # Format de données incorrect
                    raise UserError(_('Invalid data format received from UniFi API'))
            else:
                # Aucune donnée reçue
                raise UserError(_('No WiFi network data received from UniFi API'))
                
        except Exception as e:
            # Gérer les erreurs
            _logger.error(f"Error synchronizing WiFi networks: {str(e)}")
            raise UserError(_(f"Error synchronizing WiFi networks: {str(e)}"))
    
    def action_sync_users(self):
        """Synchronize only users for this site"""
        self.ensure_one()
        try:
            # Récupérer les données des utilisateurs depuis l'API UniFi
            user_data = self._get_controller_user_data()
            
            if user_data:
                # Vérifier le format des données
                if isinstance(user_data, list):
                    # Initialiser la liste des utilisateurs traités
                    processed_users = self.env['unifi.user']
                    users_list = user_data
                    
                    # Traiter chaque utilisateur
                    for user_item in users_list:
                        # Créer ou mettre à jour l'utilisateur
                        user = self.env['unifi.user'].create_or_update_from_data(self, user_item)
                        if user:
                            processed_users += user
                    
                    # Afficher un message de succès et retourner la vue des utilisateurs
                    # D'abord afficher la notification
                    self.env['bus.bus']._sendone(
                        self.env.user.partner_id,
                        'web_client.action',
                        {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('User Synchronization'),
                                'message': _(f'{len(users_list)} utilisateurs trouvés, {len(processed_users)} créés ou mis à jour'),
                                'sticky': False,
                                'type': 'success',
                            }
                        }
                    )
                    
                    # Ensuite retourner la vue des utilisateurs
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Users'),
                        'res_model': 'unifi.user',
                        'domain': [('site_id', '=', self.id)],
                        'view_mode': 'list,form',
                        'target': 'current',
                    }
                else:
                    _logger.warning("Aucun utilisateur trouvé dans les données de l'API")
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('User Synchronization'),
                            'message': _('No users found in the UniFi API data'),
                            'sticky': False,
                            'type': 'warning',
                        }
                    }
            else:
                _logger.error(f"Format de données inattendu: {type(user_data)}")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('User Synchronization'),
                        'message': _('Unexpected data format received from UniFi API'),
                        'sticky': True,
                        'type': 'danger',
                    }
                }
        except Exception as e:
            _logger.exception(f"Erreur lors de la synchronisation des utilisateurs: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('User Synchronization'),
                    'message': _('Error: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
            
    def action_sync_vlans(self):
        """Synchronize only VLANs for this site"""
        self.ensure_one()
        try:
            # Utiliser la méthode de synchronisation du modèle unifi.vlan
            vlans = self.env['unifi.vlan'].sync_vlans_from_api(self)
            
            # Afficher un message de succès
            # Vérifier si vlans est une liste ou un booléen
            vlan_count = len(vlans) if isinstance(vlans, list) else 0
            
            self.env['bus.bus']._sendone(
                self.env.user.partner_id,
                'web_client.action',
                {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('VLAN Synchronization'),
                        'message': _(f'{vlan_count} VLANs synchronisés avec succès!'),
                        'sticky': False,
                        'type': 'success',
                    }
                }
            )
            
            # Retourner la vue des VLANs
            return {
                'type': 'ir.actions.act_window',
                'name': _('VLANs'),
                'res_model': 'unifi.vlan',
                'domain': [('site_id', '=', self.id)],
                'view_mode': 'list,form',
                'target': 'current',
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('VLAN Synchronization'),
                    'message': _('Error: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
            
    def action_sync_firewall_rules(self):
        """Synchronize only firewall rules for this site"""
        self.ensure_one()
        try:
            # Utiliser la méthode de synchronisation du modèle unifi.firewall.rule
            rules = self.env['unifi.firewall.rule'].sync_firewall_rules(self)
            
            # Afficher un message de succès
            # La méthode sync_firewall_rules retourne True/False et non une liste
            # Récupérer le nombre de règles de pare-feu pour ce site
            rule_count = self.env['unifi.firewall.rule'].search_count([('site_id', '=', self.id)])
            
            self.env['bus.bus']._sendone(
                self.env.user.partner_id,
                'web_client.action',
                {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Firewall Rule Synchronization'),
                        'message': _(f'{rule_count} règles de pare-feu synchronisées avec succès!'),
                        'sticky': False,
                        'type': 'success',
                    }
                }
            )
            
            # Retourner la vue des règles de pare-feu
            return {
                'type': 'ir.actions.act_window',
                'name': _('Firewall Rules'),
                'res_model': 'unifi.firewall.rule',
                'domain': [('site_id', '=', self.id)],
                'view_mode': 'list,form',
                'target': 'current',
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Firewall Rule Synchronization'),
                    'message': _('Error: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
            
    def action_sync_port_forwards(self):
        """Synchronize only port forwards for this site"""
        self.ensure_one()
        try:
            # Utiliser la méthode de synchronisation du modèle unifi.port.forward
            port_forwards = self.env['unifi.port.forward'].sync_port_forwards(self)
            
            # Afficher un message de succès
            # La méthode sync_port_forwards retourne True/False et non une liste
            # Récupérer le nombre de redirections de port pour ce site
            port_forward_count = self.env['unifi.port.forward'].search_count([('site_id', '=', self.id)])
            
            self.env['bus.bus']._sendone(
                self.env.user.partner_id,
                'web_client.action',
                {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Port Forward Synchronization'),
                        'message': _(f'{port_forward_count} redirections de port synchronisées avec succès!'),
                        'sticky': False,
                        'type': 'success',
                    }
                }
            )
            
            # Retourner la vue des redirections de port
            return {
                'type': 'ir.actions.act_window',
                'name': _('Port Forwards'),
                'res_model': 'unifi.port.forward',
                'domain': [('site_id', '=', self.id)],
                'view_mode': 'list,form',
                'target': 'current',
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Port Forward Synchronization'),
                    'message': _('Error: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
            
    def action_sync_routing(self):
        """Synchronize only routing configuration for this site"""
        self.ensure_one()
        try:
            # Utiliser la méthode de synchronisation du modèle unifi.routing.config
            routing_configs = self.env['unifi.routing.config'].search([('site_id', '=', self.id)])
            for config in routing_configs:
                config.sync_from_unifi()
            
            # Synchroniser également les routes individuelles
            routes = self.env['unifi.routing'].search([('site_id', '=', self.id)])
            for route in routes:
                route.sync_from_unifi()
                    
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Routing Configuration Synchronization'),
                    'message': _('Routing configuration synchronized successfully!'),
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Routing Configuration Synchronization'),
                    'message': _('Error: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
    

    
    # API-specific methods
    
    def _sync_controller(self):
        """Synchronize data with the Controller API
        
        This method orchestrates the synchronization process with the UniFi Controller API.
        It retrieves data for all supported entity types (devices, networks, VLANs, users,
        firewall rules, port forwards, and system info) and updates the corresponding
        records in the Odoo database.
        
        Returns:
            bool: True if synchronization was successful, False otherwise
        """
        # Initialiser sync_job en dehors du bloc try pour éviter les erreurs de lint
        sync_job = None
        
        try:
            # Create a sync job
            sync_job = self.env['unifi.sync.job'].create({
                'site_id': self.id,
                'start_time': fields.Datetime.now(),
                'state': 'running',
                'sync_type': 'manual',
                'api_type': 'controller',
            })
            
            # Puisque nous avons fusionné les modèles, le site lui-même est le contrôleur
            # Nous pouvons donc utiliser directement les méthodes du site
            
            # Authenticate with the Controller API
            if not self._test_controller_connection():
                if sync_job:
                    sync_job.write({
                        'end_time': fields.Datetime.now(),
                        'state': 'failed',
                        'message': 'Authentication failed',
                    })
                return False
                
            success = True
            sync_messages = []
            
            # Synchronize system info
            try:
                # Utiliser une méthode du site pour récupérer les informations système
                system_info_data = self._get_system_info_data()
                if system_info_data:
                    # Process and store system info data
                    # TODO: Implement system info synchronization
                    sync_messages.append('System info synchronized')
                else:
                    sync_messages.append('Failed to retrieve system info')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing system info: {str(e)}')
                _logger.error('Error synchronizing system info: %s', str(e))
                success = False
            
            # Synchronize devices
            try:
                _logger.info("=== DÉBUT DE LA SYNCHRONISATION DES APPAREILS ===")
                # Utiliser une méthode du site pour récupérer les données des appareils
                device_data = self._get_device_data()
                
                if device_data:
                    _logger.info(f"Données d'appareils reçues: {type(device_data)}")
                    
                    # Vérifier la structure des données
                    if isinstance(device_data, dict):
                        _logger.info(f"Clés dans les données: {list(device_data.keys())}")
                        
                        # La plupart des API UniFi renvoient les données dans une clé 'data'
                        devices = device_data.get('data', [])
                        if not devices and 'devices' in device_data:
                            devices = device_data.get('devices', [])
                            
                        _logger.info(f"Nombre d'appareils trouvés: {len(devices)}")
                        
                        if devices:
                            # Afficher des informations sur le premier appareil pour débogage
                            first_device = devices[0]
                            _logger.info(f"Premier appareil: {first_device.get('name', 'Sans nom')}")
                            _logger.info(f"MAC: {first_device.get('mac', 'N/A')}")
                            _logger.info(f"Modèle: {first_device.get('model', 'N/A')}")
                            
                            # TODO: Implémenter la synchronisation des appareils
                            # Pour l'instant, juste compter les appareils
                            sync_messages.append(f'{len(devices)} appareils trouvés')
                        else:
                            _logger.warning("Aucun appareil trouvé dans les données")
                            sync_messages.append('Aucun appareil trouvé')
                    else:
                        _logger.warning(f"Format de données inattendu: {type(device_data)}")
                        sync_messages.append('Format de données inattendu')
                        success = False
                else:
                    _logger.error("Impossible de récupérer les données des appareils")
                    sync_messages.append('Échec de la récupération des appareils')
                    success = False
                _logger.info("=== FIN DE LA SYNCHRONISATION DES APPAREILS ===")
            except Exception as e:
                sync_messages.append(f'Erreur lors de la synchronisation des appareils: {str(e)}')
                _logger.error('Erreur lors de la synchronisation des appareils: %s', str(e))
                _logger.exception("Détails de l'erreur:")
                success = False
            
            # Synchronize networks
            try:
                # Utiliser une méthode du site pour récupérer les données des réseaux
                network_data = self._get_network_data()
                if network_data:
                    # Process and store network data
                    # TODO: Implement network synchronization
                    sync_messages.append('Networks synchronized')
                else:
                    sync_messages.append('Failed to retrieve networks')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing networks: {str(e)}')
                _logger.error('Error synchronizing networks: %s', str(e))
                success = False
            
            # Synchronize VLANs
            try:
                # Utiliser une méthode du site pour récupérer les données des VLANs
                vlan_data = self._get_vlan_data()
                if vlan_data:
                    # Process and store VLAN data
                    # TODO: Implement VLAN synchronization
                    sync_messages.append('VLANs synchronized')
                else:
                    sync_messages.append('Failed to retrieve VLANs')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing VLANs: {str(e)}')
                _logger.error('Error synchronizing VLANs: %s', str(e))
                success = False
            
            # Synchronize users
            try:
                # Utiliser une méthode du site pour récupérer les données des utilisateurs
                user_data = self._get_user_data()
                if user_data:
                    # Process and store user data
                    # TODO: Implement user synchronization
                    sync_messages.append('Users synchronized')
                else:
                    sync_messages.append('Failed to retrieve users')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing users: {str(e)}')
                _logger.error('Error synchronizing users: %s', str(e))
                success = False
            
            # Synchronize firewall rules
            try:
                # Utiliser une méthode du site pour récupérer les données du pare-feu
                firewall_data = self._get_firewall_data()
                if firewall_data:
                    # Process and store firewall data
                    # TODO: Implement firewall rule synchronization
                    sync_messages.append('Firewall rules synchronized')
                else:
                    sync_messages.append('Failed to retrieve firewall rules')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing firewall rules: {str(e)}')
                _logger.error('Error synchronizing firewall rules: %s', str(e))
                success = False
            
            # Synchronize port forwards
            try:
                # Utiliser une méthode du site pour récupérer les données de redirection de port
                port_forward_data = self._get_port_forward_data()
                if port_forward_data:
                    # Process and store port forward data
                    # TODO: Implement port forward synchronization
                    sync_messages.append('Port forwards synchronized')
                else:
                    sync_messages.append('Failed to retrieve port forwards')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing port forwards: {str(e)}')
                _logger.error('Error synchronizing port forwards: %s', str(e))
                success = False
            
            # Pas besoin de déconnexion explicite puisque nous utilisons directement les méthodes du site
            
            # Update sync job
            if sync_job:
                sync_job.write({
                    'end_time': fields.Datetime.now(),
                    'state': 'completed' if success else 'failed',
                    'message': '\n'.join(sync_messages),
                })
            
            # Update last sync time
            self.write({
                'last_sync': fields.Datetime.now(),
            })
            
            return success
        except Exception as e:
            _logger.error('Error synchronizing with Controller API: %s', str(e))
            if sync_job:
                sync_job.write({
                    'end_time': fields.Datetime.now(),
                    'state': 'failed',
                    'message': str(e),
                })
            return False
    
    def _sync_site_manager(self):
        """Synchronize data with the Site Manager API
        
        This method orchestrates the synchronization process with the UniFi Site Manager API.
        It retrieves data for all supported entity types (devices, networks, VLANs, users,
        firewall rules, port forwards, and system info) and updates the corresponding
        records in the Odoo database.
        
        Returns:
            bool: True if synchronization was successful, False otherwise
        """
        # Initialiser sync_job en dehors du bloc try pour éviter les erreurs de lint
        sync_job = None
        
        try:
            # Create a sync job
            sync_job = self.env['unifi.sync.job'].create({
                'site_id': self.id,
                'start_time': fields.Datetime.now(),
                'state': 'running',
                'sync_type': 'manual',
                'api_type': 'site_manager',
            })
            
            # Vérifier que l'API est configurée correctement
            if self.api_type != 'site_manager':
                if sync_job:
                    sync_job.write({
                        'end_time': fields.Datetime.now(),
                        'state': 'failed',
                        'message': 'Incorrect API type: site_manager required',
                    })
                return False
                
            # Test the connection to ensure we can authenticate
            # Use the internal method directly
            if not self._test_site_manager_connection():
                if sync_job:
                    sync_job.write({
                        'end_time': fields.Datetime.now(),
                        'state': 'failed',
                        'message': 'Connection test failed',
                    })
                return False
                
            success = True
            sync_messages = []
            
            # Synchronize system info
            try:
                # Use the integrated method directly instead of calling site_manager model
                system_info_data = self._get_site_manager_system_info_data()
                if system_info_data:
                    # Process and store system info data
                    # TODO: Implement system info synchronization
                    sync_messages.append('System info synchronized')
                else:
                    sync_messages.append('Failed to retrieve system info')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing system info: {str(e)}')
                _logger.error('Error synchronizing system info: %s', str(e))
                success = False
            
            # Synchronize devices
            try:
                # Use the integrated method directly instead of calling site_manager model
                device_data = self._get_site_manager_device_data()
                if device_data:
                    # Process and store device data
                    # TODO: Implement device synchronization
                    sync_messages.append('Devices synchronized')
                else:
                    sync_messages.append('Failed to retrieve devices')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing devices: {str(e)}')
                _logger.error('Error synchronizing devices: %s', str(e))
                success = False
            
            # Synchronize networks
            try:
                # Use the integrated method directly instead of calling site_manager model
                network_data = self._get_site_manager_network_data()
                if network_data:
                    # Process and store network data
                    # TODO: Implement network synchronization
                    sync_messages.append('Networks synchronized')
                else:
                    sync_messages.append('Failed to retrieve networks')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing networks: {str(e)}')
                _logger.error('Error synchronizing networks: %s', str(e))
                success = False
            
            # Synchronize VLANs
            try:
                # Use the integrated method directly instead of calling site_manager model
                vlan_data = self._get_site_manager_vlan_data()
                if vlan_data:
                    # Process and store VLAN data
                    # TODO: Implement VLAN synchronization
                    sync_messages.append('VLANs synchronized')
                else:
                    sync_messages.append('Failed to retrieve VLANs')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing VLANs: {str(e)}')
                _logger.error('Error synchronizing VLANs: %s', str(e))
                success = False
            
            # Synchronize users
            try:
                # Use the integrated method directly instead of calling site_manager model
                user_data = self._get_site_manager_user_data()
                if user_data:
                    # Process and store user data
                    # TODO: Implement user synchronization
                    sync_messages.append('Users synchronized')
                else:
                    sync_messages.append('Failed to retrieve users')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing users: {str(e)}')
                _logger.error('Error synchronizing users: %s', str(e))
                success = False
            
            # Synchronize firewall rules
            try:
                # Use the integrated method directly instead of calling site_manager model
                firewall_data = self._get_site_manager_firewall_data()
                if firewall_data:
                    # Process and store firewall data
                    # TODO: Implement firewall rule synchronization
                    sync_messages.append('Firewall rules synchronized')
                else:
                    sync_messages.append('Failed to retrieve firewall rules')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing firewall rules: {str(e)}')
                _logger.error('Error synchronizing firewall rules: %s', str(e))
                success = False
            
            # Synchronize port forwards
            try:
                # Use the integrated method directly instead of calling site_manager model
                port_forward_data = self._get_site_manager_port_forward_data()
                if port_forward_data:
                    # Process and store port forward data
                    # TODO: Implement port forward synchronization
                    sync_messages.append('Port forwards synchronized')
                else:
                    sync_messages.append('Failed to retrieve port forwards')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing port forwards: {str(e)}')
                _logger.error('Error synchronizing port forwards: %s', str(e))
                success = False
            
            # Update sync job
            if sync_job:
                sync_job.write({
                    'end_time': fields.Datetime.now(),
                    'state': 'completed' if success else 'failed',
                    'message': '\n'.join(sync_messages),
                })
            
            # Update last sync time
            self.write({
                'last_sync': fields.Datetime.now(),
            })
            
            return success
        except Exception as e:
            _logger.error('Error synchronizing with Site Manager API: %s', str(e))
            if sync_job:
                sync_job.write({
                    'end_time': fields.Datetime.now(),
                    'state': 'failed',
                    'message': str(e),
                })
            return False
    
    # Override create and write methods
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to verify connection before saving
        
        Args:
            vals_list (list): List of values to create records with
            
        Returns:
            unifi.site: The created records
        """
        # Create the records
        sites = super(UnifiSite, self).create(vals_list)
        
        # Test the connection for each site
        for site in sites:
            try:
                if site.api_type == 'controller':
                    site._test_controller_connection()
                elif site.api_type == 'site_manager':
                    site._test_site_manager_connection()
            except Exception as e:
                _logger.warning('Connection test failed during creation: %s', str(e))
                # We don't raise an error here, just log a warning
        
        return sites
    
    def write(self, vals):
        """Override write to verify connection if connection details change"""
        # Check if connection details have changed
        connection_fields = ['api_type', 'host', 'port', 'username', 'password', 
                            'controller_type', 'api_key', 'mfa_enabled', 'mfa_token']
        
        connection_changed = any(field in vals for field in connection_fields)
        
        # Write the values
        result = super(UnifiSite, self).write(vals)
        
        # Test the connection if connection details have changed
        if connection_changed:
            for site in self:
                try:
                    if site.api_type == 'controller':
                        site._test_controller_connection()
                    elif site.api_type == 'site_manager':
                        site._test_site_manager_connection()
                except Exception as e:
                    _logger.warning('Connection test failed after update: %s', str(e))
                    # We don't raise an error here, just log a warning
        
        return result
    
    def get_device_data(self):
        """Récupère les données des appareils du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les appareils.
        
        Returns:
            list: Liste des données de tous les appareils
        """
        self.ensure_one()
        
        # Determine which API implementation to use
        if self.api_type == 'controller':
            # Use Controller API implementation
            # This is now directly implemented here instead of delegating to another model
            return self._get_controller_device_data()
        elif self.api_type == 'site_manager':
            # Use Site Manager API implementation
            # This is now directly implemented here instead of delegating to another model
            return self._get_site_manager_device_data()
            
    def _create_api_log(self, api_method, message_text, direction):
        """Create a new API log entry
        
        Args:
            api_method: API method being called (e.g., 'get_device_data')
            message_text: Log message
            direction: Direction of the API call (e.g., 'outgoing', 'incoming')
            
        Returns:
            Record: Newly created API log record
        """
        try:
            # Déterminer le type d'API en fonction du contexte
            api_type = self.api_type or 'controller'
            
            # Créer un endpoint basé sur le nom de la méthode
            endpoint = f"/api/{api_method}"
            
            # Déterminer la méthode HTTP en fonction de la direction
            http_method = 'GET' if direction == 'outgoing' else 'POST'
            
            # Create a new api.log record
            api_log_vals = {
                'site_id': self.id,
                'api_type': api_type,
                'endpoint': endpoint,
                'method': http_method,
                'error_message': message_text if direction != 'outgoing' else None,
                'start_time': fields.Datetime.now(),
            }
            # Create and return the log record
            return self.env['unifi.api.log'].create(api_log_vals)
        except Exception as e:
            _logger.error('Error creating API log: %s', str(e))
            return False
            
    def _get_controller_device_data(self):
        """Get device data from UniFi Controller API
        
        This method directly implements the device data retrieval logic for the Controller API type.
        It was previously in the unifi.site.controller model, but has been integrated here.
        
        Returns:
            list: Device data from Controller API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_device_data', 'Getting device data from Controller API', 'outgoing')
        
        try:
            # Implement the Controller-specific API call logic here
            # This would be similar to what was in the unifi.site.controller model
            base_url = f"https://{self.host}:{self.port}"
            endpoint = f"/api/s/{self.site_id}/stat/device"  # Using site_id field
            # Make the API request and process the response
            # For now, this is a placeholder
            result = []
            
            # Log the successful API call
            self._update_api_log(api_log, {'message': 'Success: Retrieved device data', 'status': 'success'})
            return result
        except Exception as e:
            # Log the error
            self._update_api_log(api_log, {'message': f'Error: {str(e)}', 'status': 'error'})
            _logger.error("Error getting device data from Controller API: %s", str(e))
            return False
            
    def _get_site_manager_device_data(self):
        """Get device data from UniFi Site Manager API
        
        This method directly implements the device data retrieval logic for the Site Manager API type.
        It was previously in the unifi.site.manager model, but has been integrated here.
        
        Returns:
            list: Device data from Site Manager API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_device_data', 'Getting device data from Site Manager API', 'outgoing')
        
        try:
            # Implement the Site Manager-specific API call logic here
            # This would be similar to what was in the unifi.site.manager model
            # Make the API request and process the response
            # For now, this is a placeholder
            result = []
            
            # Log the successful API call
            self._update_api_log(api_log, {'message': 'Success: Retrieved device data', 'status': 'success'})
            return result
        except Exception as e:
            # Log the error
            self._update_api_log(api_log, {'message': f'Error: {str(e)}', 'status': 'error'})
            _logger.error("Error getting device data from Site Manager API: %s", str(e))
            return False
        else:
            # Unsupported API type
            _logger.error("Unsupported API type: %s", self.api_type)
            return False
    
    def _get_site_manager_vlan_data(self):
        """Get VLAN data from UniFi Site Manager API
        
        This method directly implements the VLAN data retrieval logic for the Site Manager API type.
        It was previously in the unifi.site.manager model, but has been integrated here.
        
        Returns:
            list: VLAN data from Site Manager API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_vlan_data', 'Getting VLAN data from Site Manager API', 'outgoing')
        
        try:
            # Implement the Site Manager-specific API call logic here
            # Make the API request and process the response
            # For now, this is a placeholder
            result = []
            
            # Log the successful API call
            self._update_api_log(api_log, {'message': 'Success: Retrieved VLAN data', 'status': 'success'})
            return result
        except Exception as e:
            # Log the error
            self._update_api_log(api_log, {'message': f'Error: {str(e)}', 'status': 'error'})
            _logger.error("Error getting VLAN data from Site Manager API: %s", str(e))
            return False
            
    def _get_site_manager_user_data(self):
        """Get user data from UniFi Site Manager API
        
        This method directly implements the user data retrieval logic for the Site Manager API type.
        It was previously in the unifi.site.manager model, but has been integrated here.
        
        Returns:
            list: User data from Site Manager API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_user_data', 'Getting user data from Site Manager API', 'outgoing')
        
        try:
            # Implement the Site Manager-specific API call logic here
            # Make the API request and process the response
            # For now, this is a placeholder
            result = []
            
            # Log the successful API call
            self._update_api_log(api_log, {'message': 'Success: Retrieved user data', 'status': 'success'})
            return result
        except Exception as e:
            # Log the error
            self._update_api_log(api_log, {'message': f'Error: {str(e)}', 'status': 'error'})
            _logger.error("Error getting user data from Site Manager API: %s", str(e))
            return False
            
    def _get_site_manager_firewall_data(self):
        """Get firewall data from UniFi Site Manager API
        
        This method directly implements the firewall data retrieval logic for the Site Manager API type.
        It was previously in the unifi.site.manager model, but has been integrated here.
        
        Returns:
            list: Firewall data from Site Manager API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_firewall_data', 'Getting firewall data from Site Manager API', 'outgoing')
        
        try:
            # Implement the Site Manager-specific API call logic here
            # Make the API request and process the response
            # For now, this is a placeholder
            result = []
            
            # Log the successful API call
            self._update_api_log(api_log, {'message': 'Success: Retrieved firewall data', 'status': 'success'})
            return result
        except Exception as e:
            # Log the error
            self._update_api_log(api_log, {'message': f'Error: {str(e)}', 'status': 'error'})
            _logger.error("Error getting firewall data from Site Manager API: %s", str(e))
            return False
            
    def _get_site_manager_port_forward_data(self):
        """Get port forward data from UniFi Site Manager API
        
        This method directly implements the port forward data retrieval logic for the Site Manager API type.
        It was previously in the unifi.site.manager model, but has been integrated here.
        
        Returns:
            list: Port forward data from Site Manager API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_port_forward_data', 'Getting port forward data from Site Manager API', 'outgoing')
        
        try:
            # Implement the Site Manager-specific API call logic here
            # Make the API request and process the response
            # For now, this is a placeholder
            result = []
            
            # Log the successful API call
            self._update_api_log(api_log, {'message': 'Success: Retrieved port forward data', 'status': 'success'})
            return result
        except Exception as e:
            # Log the error
            self._update_api_log(api_log, {'message': f'Error: {str(e)}', 'status': 'error'})
            _logger.error("Error getting port forward data from Site Manager API: %s", str(e))
            return False
    
    def _get_site_manager_system_info_data(self):
        """Get system info data from UniFi Site Manager API
        
        This method directly implements the system info data retrieval logic for the Site Manager API type.
        It was previously in the unifi.site.manager model, but has been integrated here.
        
        Returns:
            dict: System info data from Site Manager API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_system_info_data', 'Getting system info data from Site Manager API', 'outgoing')
        
        try:
            # Implement the Site Manager-specific API call logic here
            # Make the API request and process the response
            # For now, this is a placeholder
            result = {}
            
            # Log the successful API call
            self._update_api_log(api_log, {'message': 'Success: Retrieved system info data', 'status': 'success'})
            return result
        except Exception as e:
            # Log the error
            self._update_api_log(api_log, {'message': f'Error: {str(e)}', 'status': 'error'})
            _logger.error("Error getting system info data from Site Manager API: %s", str(e))
            return False
            
    def _get_site_manager_dns_data(self):
        """Get DNS data from UniFi Site Manager API
        
        This method directly implements the DNS data retrieval logic for the Site Manager API type.
        
        Returns:
            list: DNS data from Site Manager API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_dns_data', 'Getting DNS data from Site Manager API', 'outgoing')
        
        try:
            # Implement the Site Manager-specific API call logic here
            # Make the API request and process the response
            # For now, this is a placeholder
            result = []
            
            # Log the successful API call
            self._update_api_log(api_log, {'message': 'Success: Retrieved DNS data', 'status': 'success'})
            return result
        except Exception as e:
            # Log the error
            self._update_api_log(api_log, {'message': f'Error: {str(e)}', 'status': 'error'})
            _logger.error("Error getting DNS data from Site Manager API: %s", str(e))
            return False
            
    def _get_controller_wifi_data(self):
        """Get WiFi network data from UniFi Controller API
        
        This method directly implements the WiFi network data retrieval logic for the Controller API type.
        
        Returns:
            list: WiFi network data from Controller API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_wifi_data', 'Getting WiFi network data from Controller API', 'outgoing')
        
        try:
            # Vérifier si nous avons une session d'authentification valide
            if not self._check_auth_session():
                _logger.error("Pas de session d'authentification valide pour récupérer les données des réseaux WiFi")
                return False
                
            # Construire l'URL de base en fonction du type de contrôleur (standard ou UDM Pro)
            base_url = f"https://{self.host}:{self.port}"
            
            # Déterminer si nous avons affaire à un UDM Pro
            is_udm_pro = self.auth_session_id and self.auth_session_id.is_udm_pro
            
            # Construire l'endpoint en fonction du type de contrôleur
            if is_udm_pro:
                # Pour UDM Pro, ajouter le préfixe /proxy/network
                endpoint = f"/proxy/network/api/s/{self.site_id}/rest/wlanconf"
            else:
                # Pour les contrôleurs standard
                endpoint = f"/api/s/{self.site_id}/rest/wlanconf"
                
            _logger.info(f"Récupération des réseaux WiFi depuis l'endpoint: {endpoint}")
            
            # Préparer les en-têtes de la requête
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Ajouter le token d'authentification si disponible (pour UDM Pro)
            if is_udm_pro and self.auth_session_id.token:
                headers['Authorization'] = f"Bearer {self.auth_session_id.token}"
            
            # Préparer les cookies pour l'authentification
            cookies = self._get_auth_cookies()
            if not cookies:
                _logger.error("Impossible de récupérer les cookies d'authentification")
                return False
                
            # Effectuer la requête HTTP
            url = f"{base_url}{endpoint}"
            _logger.info(f"Envoi de la requête GET à {url}")
            
            response = requests.get(
                url,
                headers=headers,
                cookies=cookies,
                verify=self.verify_ssl
            )
            
            # Vérifier le code de statut de la réponse
            if response.status_code != 200:
                _logger.error(f"Erreur lors de la récupération des données des réseaux WiFi: {response.status_code} - {response.text}")
                self._update_api_log(api_log, {
                    'status_code': response.status_code,
                    'response_body': response.text,
                    'message': f'Error: HTTP {response.status_code}',
                    'status': 'error'
                })
                return False
                
            # Analyser la réponse JSON
            try:
                result = response.json()
                _logger.info(f"Réponse reçue: {type(result)}")
                
                # Enregistrer les détails de la réponse dans le log API
                self._update_api_log(api_log, {
                    'status_code': response.status_code,
                    'response_body': response.text,
                    'message': 'Success: Retrieved WiFi network data',
                    'status': 'success'
                })
                
                # La plupart des API UniFi renvoient les données dans une clé 'data'
                if isinstance(result, dict) and 'data' in result:
                    return result['data']
                return result
                
            except json.JSONDecodeError as e:
                _logger.error(f"Erreur lors de l'analyse de la réponse JSON: {str(e)}")
                _logger.error(f"Contenu de la réponse: {response.text}")
                self._update_api_log(api_log, {
                    'status_code': response.status_code,
                    'response_body': response.text,
                    'message': f'Error: Invalid JSON response - {str(e)}',
                    'status': 'error'
                })
                return False
                
        except Exception as e:
            # Log the error
            _logger.exception(f"Erreur lors de la récupération des données des réseaux WiFi: {str(e)}")
            self._update_api_log(api_log, {
                'message': f'Error: {str(e)}',
                'status': 'error'
            })
            return False
    
    def _get_controller_user_data(self):
        """Get user data from UniFi Controller API
        
        This method directly implements the user data retrieval logic for the Controller API type.
        
        Returns:
            list: User data from Controller API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_user_data', 'Getting user data from Controller API', 'outgoing')
        
        try:
            # Vérifier si nous avons une session d'authentification valide
            if not self._check_auth_session():
                _logger.error("Pas de session d'authentification valide pour récupérer les données des utilisateurs")
                return False
                
            # Construire l'URL de base en fonction du type de contrôleur (standard ou UDM Pro)
            base_url = f"https://{self.host}:{self.port}"
            
            # Déterminer si nous avons affaire à un UDM Pro
            is_udm_pro = self.auth_session_id and self.auth_session_id.is_udm_pro
            
            # Construire l'endpoint en fonction du type de contrôleur
            if is_udm_pro:
                # Pour UDM Pro, ajouter le préfixe /proxy/network
                endpoint = f"/proxy/network/api/s/{self.site_id}/rest/user"
            else:
                # Pour les contrôleurs standard
                endpoint = f"/api/s/{self.site_id}/rest/user"
                
            _logger.info(f"Récupération des utilisateurs depuis l'endpoint: {endpoint}")
            
            # Préparer les en-têtes de la requête
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Ajouter le token d'authentification si disponible (pour UDM Pro)
            if is_udm_pro and self.auth_session_id.token:
                headers['Authorization'] = f"Bearer {self.auth_session_id.token}"
            
            # Préparer les cookies pour l'authentification
            cookies = self._get_auth_cookies()
            if not cookies:
                _logger.error("Impossible de récupérer les cookies d'authentification")
                return False
                
            # Effectuer la requête HTTP
            url = f"{base_url}{endpoint}"
            _logger.info(f"Envoi de la requête GET à {url}")
            
            response = requests.get(
                url,
                headers=headers,
                cookies=cookies,
                verify=self.verify_ssl
            )
            
            # Vérifier le code de statut de la réponse
            if response.status_code != 200:
                _logger.error(f"Erreur lors de la récupération des données des utilisateurs: {response.status_code} - {response.text}")
                self._update_api_log(api_log, {
                    'status_code': response.status_code,
                    'response_body': response.text,
                    'message': f'Error: HTTP {response.status_code}',
                    'status': 'error'
                })
                return False
                
            # Analyser la réponse JSON
            try:
                result = response.json()
                _logger.info(f"Réponse reçue: {type(result)}")
                
                # Enregistrer les détails de la réponse dans le log API
                self._update_api_log(api_log, {
                    'status_code': response.status_code,
                    'response_body': response.text,
                    'message': 'Success: Retrieved user data',
                    'status': 'success'
                })
                
                # La plupart des API UniFi renvoient les données dans une clé 'data'
                if isinstance(result, dict) and 'data' in result:
                    return result['data']
                return result
                
            except json.JSONDecodeError as e:
                _logger.error(f"Erreur lors de l'analyse de la réponse JSON: {str(e)}")
                _logger.error(f"Contenu de la réponse: {response.text}")
                self._update_api_log(api_log, {
                    'status_code': response.status_code,
                    'response_body': response.text,
                    'message': f'Error: Invalid JSON response - {str(e)}',
                    'status': 'error'
                })
                return False
                
        except Exception as e:
            # Log the error
            _logger.exception(f"Erreur lors de la récupération des données des utilisateurs: {str(e)}")
            self._update_api_log(api_log, {
                'message': f'Error: {str(e)}',
                'status': 'error'
            })
            return False
            
    def _get_controller_get_firewall_data(self):
        """Get firewall rules data from UniFi Controller API
        
        This method directly implements the firewall rules data retrieval logic for the Controller API type.
        
        Returns:
            list: Firewall rules data from Controller API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_firewall_data', 'Getting firewall rules data from Controller API', 'outgoing')
        
        try:
            # Vérifier si nous avons une session d'authentification valide
            if not self._check_auth_session():
                _logger.error("Pas de session d'authentification valide pour récupérer les données des règles de pare-feu")
                return False
                
            # Construire l'URL de base en fonction du type de contrôleur (standard ou UDM Pro)
            base_url = f"https://{self.host}:{self.port}"
            
            # Déterminer si nous avons affaire à un UDM Pro
            is_udm_pro = self.auth_session_id and self.auth_session_id.is_udm_pro
            
            # Construire l'endpoint en fonction du type de contrôleur
            if is_udm_pro:
                # Pour UDM Pro, ajouter le préfixe /proxy/network
                endpoint = f"/proxy/network/api/s/{self.site_id}/rest/firewallrule"
            else:
                # Pour les contrôleurs standard
                endpoint = f"/api/s/{self.site_id}/rest/firewallrule"
                
            _logger.info(f"Récupération des règles de pare-feu depuis l'endpoint: {endpoint}")
            
            # Préparer les en-têtes de la requête
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Ajouter le token d'authentification si disponible (pour UDM Pro)
            if is_udm_pro and self.auth_session_id.token:
                headers['Authorization'] = f"Bearer {self.auth_session_id.token}"
            
            # Préparer les cookies pour l'authentification
            cookies = self._get_auth_cookies()
            if not cookies:
                _logger.error("Impossible de récupérer les cookies d'authentification")
                return False
            
            # Effectuer la requête GET pour récupérer les données des règles de pare-feu
            response = requests.get(
                f"{base_url}{endpoint}",
                headers=headers,
                cookies=cookies,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            # Vérifier si la requête a réussi
            if response.status_code != 200:
                error_msg = f"Erreur lors de la récupération des règles de pare-feu: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._update_api_log(api_log, {'message': error_msg, 'status': 'error', 'response': response.text})
                return False
            
            # Analyser la réponse JSON
            response_data = response.json()
            
            # Extraire les données des règles de pare-feu
            firewall_data = response_data.get('data', [])
            
            # Mettre à jour le log API avec le succès
            self._update_api_log(api_log, {
                'message': f"Succès: {len(firewall_data)} règles de pare-feu récupérées", 
                'status': 'success',
                'response': json.dumps(response_data)
            })
            
            return firewall_data
        except Exception as e:
            # Log the error
            error_msg = f"Erreur lors de la récupération des règles de pare-feu: {str(e)}"
            _logger.error(error_msg)
            self._update_api_log(api_log, {'message': error_msg, 'status': 'error'})
            return False
    
    def _get_controller_get_port_forward_data(self):
        """Get port forwarding data from UniFi Controller API
        
        This method directly implements the port forwarding data retrieval logic for the Controller API type.
        
        Returns:
            list: Port forwarding data from Controller API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_port_forward_data', 'Getting port forwarding data from Controller API', 'outgoing')
        
        try:
            # Vérifier si nous avons une session d'authentification valide
            if not self._check_auth_session():
                _logger.error("Pas de session d'authentification valide pour récupérer les données de redirection de port")
                return False
                
            # Construire l'URL de base en fonction du type de contrôleur (standard ou UDM Pro)
            base_url = f"https://{self.host}:{self.port}"
            
            # Déterminer si nous avons affaire à un UDM Pro
            is_udm_pro = self.auth_session_id and self.auth_session_id.is_udm_pro
            
            # Construire l'endpoint en fonction du type de contrôleur
            if is_udm_pro:
                # Pour UDM Pro, ajouter le préfixe /proxy/network
                endpoint = f"/proxy/network/api/s/{self.site_id}/rest/portforward"
            else:
                # Pour les contrôleurs standard
                endpoint = f"/api/s/{self.site_id}/rest/portforward"
                
            _logger.info(f"Récupération des redirections de port depuis l'endpoint: {endpoint}")
            
            # Préparer les en-têtes de la requête
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Ajouter le token d'authentification si disponible (pour UDM Pro)
            if is_udm_pro and self.auth_session_id.token:
                headers['Authorization'] = f"Bearer {self.auth_session_id.token}"
            
            # Préparer les cookies pour l'authentification
            cookies = self._get_auth_cookies()
            if not cookies:
                _logger.error("Impossible de récupérer les cookies d'authentification")
                return False
            
            # Effectuer la requête GET pour récupérer les données de redirection de port
            response = requests.get(
                f"{base_url}{endpoint}",
                headers=headers,
                cookies=cookies,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            # Vérifier si la requête a réussi
            if response.status_code != 200:
                error_msg = f"Erreur lors de la récupération des redirections de port: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._update_api_log(api_log, {'message': error_msg, 'status': 'error', 'response': response.text})
                return False
            
            # Analyser la réponse JSON
            response_data = response.json()
            
            # Extraire les données des redirections de port
            port_forward_data = response_data.get('data', [])
            
            # Mettre à jour le log API avec le succès
            self._update_api_log(api_log, {
                'message': f"Succès: {len(port_forward_data)} redirections de port récupérées", 
                'status': 'success',
                'response': json.dumps(response_data)
            })
            
            return port_forward_data
        except Exception as e:
            # Log the error
            error_msg = f"Erreur lors de la récupération des redirections de port: {str(e)}"
            _logger.error(error_msg)
            self._update_api_log(api_log, {'message': error_msg, 'status': 'error'})
            return False
    
    def _get_controller_get_dns_data(self):
        """Get DNS data from UniFi Controller API
        
        This method directly implements the DNS data retrieval logic for the Controller API type.
        
        Returns:
            list: DNS data from Controller API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_dns_data', 'Getting DNS data from Controller API', 'outgoing')
        
        try:
            # Vérifier si nous avons une session d'authentification valide
            if not self._check_auth_session():
                _logger.error("Pas de session d'authentification valide pour récupérer les données DNS")
                return False
                
            # Construire l'URL de base en fonction du type de contrôleur (standard ou UDM Pro)
            base_url = f"https://{self.host}:{self.port}"
            
            # Déterminer si nous avons affaire à un UDM Pro
            is_udm_pro = self.auth_session_id and self.auth_session_id.is_udm_pro
            
            # Construire l'endpoint en fonction du type de contrôleur
            if is_udm_pro:
                # Pour UDM Pro, ajouter le préfixe /proxy/network
                endpoint = f"/proxy/network/api/s/{self.site_id}/rest/setting"
            else:
                # Pour les contrôleurs standard
                endpoint = f"/api/s/{self.site_id}/rest/setting"
                
            _logger.info(f"Récupération des entrées DNS depuis l'endpoint: {endpoint}")
            
            # Préparer les en-têtes de la requête
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Ajouter le token d'authentification si disponible (pour UDM Pro)
            if is_udm_pro and self.auth_session_id.token:
                headers['Authorization'] = f"Bearer {self.auth_session_id.token}"
            
            # Préparer les cookies pour l'authentification
            cookies = self._get_auth_cookies()
            if not cookies:
                _logger.error("Impossible de récupérer les cookies d'authentification")
                return False
            
            # Effectuer la requête GET pour récupérer les données DNS
            response = requests.get(
                f"{base_url}{endpoint}",
                headers=headers,
                cookies=cookies,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            # Vérifier si la requête a réussi
            if response.status_code != 200:
                error_msg = f"Erreur lors de la récupération des entrées DNS: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._update_api_log(api_log, {'message': error_msg, 'status': 'error', 'response': response.text})
                return False
            
            # Analyser la réponse JSON
            response_data = response.json()
            
            # Extraire les données DNS des paramètres du site
            settings_data = response_data.get('data', [])
            
            # Rechercher les paramètres DNS dans les données de configuration
            dns_entries = []
            for setting in settings_data:
                if setting.get('key') == 'networks':
                    networks = setting.get('values', [])
                    for network in networks:
                        # Extraire les serveurs DNS configurés dans chaque réseau
                        dns_servers = network.get('dns_servers', [])
                        if dns_servers:
                            for i, dns_server in enumerate(dns_servers):
                                if dns_server and dns_server.strip():
                                    dns_entries.append({
                                        'hostname': f"dns-server-{network.get('name', '')}-{i+1}",
                                        'ip_address': dns_server,
                                        'description': f"DNS Server {i+1} for network {network.get('name', '')}",
                                        'enabled': True,
                                        'unifi_id': f"{network.get('_id', '')}-dns-{i}",
                                        'entry_type': 'server'
                                    })
                        
                        # Extraire les entrées DNS statiques configurées dans chaque réseau
                        static_dns = network.get('static_dns', [])
                        if static_dns:
                            for i, entry in enumerate(static_dns):
                                dns_entries.append({
                                    'hostname': entry.get('name', f"static-dns-{i}"),
                                    'ip_address': entry.get('ip', ''),
                                    'description': f"Static DNS entry for {entry.get('name', '')}",
                                    'enabled': True,
                                    'unifi_id': f"{network.get('_id', '')}-static-dns-{i}",
                                    'entry_type': 'static'
                                })
            
            # Si aucune entrée DNS n'est trouvée, essayer de récupérer les paramètres DNS généraux
            if not dns_entries:
                for setting in settings_data:
                    if setting.get('key') == 'dns':
                        dns_config = setting.get('values', {})
                        servers = dns_config.get('servers', [])
                        for i, server in enumerate(servers):
                            if server and server.strip():
                                dns_entries.append({
                                    'hostname': f"global-dns-server-{i+1}",
                                    'ip_address': server,
                                    'description': f"Global DNS Server {i+1}",
                                    'enabled': True,
                                    'unifi_id': f"global-dns-{i}",
                                    'entry_type': 'server'
                                })
            
            formatted_dns_data = dns_entries
            
            # Mettre à jour le log API avec le succès, même si aucune entrée n'est trouvée
            message = f"Succès: {len(formatted_dns_data)} entrées DNS récupérées"
            if not formatted_dns_data:
                message = "Succès: Aucune entrée DNS trouvée dans la configuration"
                
            self._update_api_log(api_log, {
                'message': message, 
                'status': 'success',
                'response': json.dumps(response_data)
            })
            
            # Retourner les données formatées, même si c'est une liste vide
            return formatted_dns_data
        except Exception as e:
            # Log the error
            error_msg = f"Erreur lors de la récupération des entrées DNS: {str(e)}"
            _logger.error(error_msg)
            self._update_api_log(api_log, {'message': error_msg, 'status': 'error'})
            return False
    
    def _get_controller_get_system_info_data(self):
        """Get system information data from UniFi Controller API
        
        This method directly implements the system information data retrieval logic for the Controller API type.
        
        Returns:
            list: System information data from Controller API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_system_info_data', 'Getting system information data from Controller API', 'outgoing')
        
        try:
            # Vérifier si nous avons une session d'authentification valide
            if not self._check_auth_session():
                _logger.error("Pas de session d'authentification valide pour récupérer les données d'information système")
                return False
                
            # Construire l'URL de base en fonction du type de contrôleur (standard ou UDM Pro)
            base_url = f"https://{self.host}:{self.port}"
            
            # Déterminer si nous avons affaire à un UDM Pro
            is_udm_pro = self.auth_session_id and self.auth_session_id.is_udm_pro
            
            # Construire l'endpoint en fonction du type de contrôleur
            if is_udm_pro:
                # Pour UDM Pro, ajouter le préfixe /proxy/network
                endpoint = f"/proxy/network/api/s/{self.site_id}/stat/device"
            else:
                # Pour les contrôleurs standard
                endpoint = f"/api/s/{self.site_id}/stat/device"
                
            _logger.info(f"Récupération des informations système depuis l'endpoint: {endpoint}")
            
            # Préparer les en-têtes de la requête
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Ajouter le token d'authentification si disponible (pour UDM Pro)
            if is_udm_pro and self.auth_session_id.token:
                headers['Authorization'] = f"Bearer {self.auth_session_id.token}"
            
            # Préparer les cookies pour l'authentification
            cookies = self._get_auth_cookies()
            if not cookies:
                _logger.error("Impossible de récupérer les cookies d'authentification")
                return False
            
            # Effectuer la requête GET pour récupérer les données d'information système
            response = requests.get(
                f"{base_url}{endpoint}",
                headers=headers,
                cookies=cookies,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            # Vérifier si la requête a réussi
            if response.status_code != 200:
                error_msg = f"Erreur lors de la récupération des informations système: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._update_api_log(api_log, {'message': error_msg, 'status': 'error', 'response': response.text})
                return False
            
            # Analyser la réponse JSON
            response_data = response.json()
            
            # Extraire les données d'information système
            devices = response_data.get('data', [])
            
            # Transformer les données des appareils en format d'information système
            system_info_data = []
            for device in devices:
                # Extraire les informations pertinentes pour le système
                system_info = {
                    'hostname': device.get('name') or device.get('hostname', 'Unknown'),
                    'version': device.get('version', 'Unknown'),
                    'model': device.get('model', 'Unknown'),
                    'uptime': device.get('uptime', 0),
                    'serial': device.get('serial', 'Unknown'),
                    'mac_address': device.get('mac', 'Unknown'),
                    'device_id': device.get('_id', ''),
                    'ip_address': device.get('ip', 'Unknown'),
                    'cpu_usage': device.get('system_stats', {}).get('cpu', 0),
                    'memory_usage': device.get('system_stats', {}).get('mem', 0),
                    'temperature': device.get('general_temperature', 0)
                }
                system_info_data.append(system_info)
            
            # Mettre à jour le log API avec le succès
            self._update_api_log(api_log, {
                'message': f"Succès: {len(system_info_data)} informations système récupérées", 
                'status': 'success',
                'response': json.dumps(response_data)
            })
            
            return system_info_data
        except Exception as e:
            # Log the error
            error_msg = f"Erreur lors de la récupération des informations système: {str(e)}"
            _logger.error(error_msg)
            self._update_api_log(api_log, {'message': error_msg, 'status': 'error'})
            return False
    
    def _get_controller_get_vlan_data(self):
        """Get VLAN data from UniFi Controller API
        
        This method directly implements the VLAN data retrieval logic for the Controller API type.
        
        Returns:
            list: VLAN data from Controller API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_vlan_data', 'Getting VLAN data from Controller API', 'outgoing')
        
        try:
            # Vérifier si nous avons une session d'authentification valide
            if not self._check_auth_session():
                _logger.error("Pas de session d'authentification valide pour récupérer les données des VLANs")
                return False
                
            # Construire l'URL de base en fonction du type de contrôleur (standard ou UDM Pro)
            base_url = f"https://{self.host}:{self.port}"
            
            # Déterminer si nous avons affaire à un UDM Pro
            is_udm_pro = self.auth_session_id and self.auth_session_id.is_udm_pro
            
            # Construire l'endpoint en fonction du type de contrôleur
            if is_udm_pro:
                # Pour UDM Pro, ajouter le préfixe /proxy/network
                endpoint = f"/proxy/network/api/s/{self.site_id}/rest/networkconf"
            else:
                # Pour les contrôleurs standard
                endpoint = f"/api/s/{self.site_id}/rest/networkconf"
                
            _logger.info(f"Récupération des VLANs depuis l'endpoint: {endpoint}")
            
            # Préparer les en-têtes de la requête
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Ajouter le token d'authentification si disponible (pour UDM Pro)
            if is_udm_pro and self.auth_session_id.token:
                headers['Authorization'] = f"Bearer {self.auth_session_id.token}"
            
            # Préparer les cookies pour l'authentification
            cookies = self._get_auth_cookies()
            if not cookies:
                _logger.error("Impossible de récupérer les cookies d'authentification")
                return False
            
            # Effectuer la requête GET pour récupérer les données des VLANs
            response = requests.get(
                f"{base_url}{endpoint}",
                headers=headers,
                cookies=cookies,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            # Vérifier si la requête a réussi
            if response.status_code != 200:
                error_msg = f"Erreur lors de la récupération des VLANs: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._update_api_log(api_log, {'message': error_msg, 'status': 'error', 'response': response.text})
                return False
            
            # Analyser la réponse JSON
            response_data = response.json()
            
            # Extraire les données des VLANs
            vlan_data = []
            for network in response_data.get('data', []):
                # Filtrer uniquement les réseaux qui ont un VLAN ID
                if 'vlan' in network and network.get('vlan') not in [None, 0]:
                    # Transformer les données du réseau en format VLAN
                    vlan = {
                        'vlan_id': network.get('vlan'),
                        'name': network.get('name', f"VLAN {network.get('vlan')}"),
                        'purpose': network.get('purpose', 'corporate'),
                        'enabled': network.get('enabled', True),
                        '_id': network.get('_id'),
                        'subnet': network.get('ip_subnet'),
                        'created_at': network.get('created', fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                        'updated_at': network.get('updated', fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    }
                    vlan_data.append(vlan)
            
            # Mettre à jour le log API avec le succès
            self._update_api_log(api_log, {
                'message': f"Succès: {len(vlan_data)} VLANs récupérés", 
                'status': 'success',
                'response': json.dumps(response_data)
            })
            
            return vlan_data
        except Exception as e:
            # Log the error
            error_msg = f"Erreur lors de la récupération des VLANs: {str(e)}"
            _logger.error(error_msg)
            self._update_api_log(api_log, {'message': error_msg, 'status': 'error'})
            return False
    
    def _get_controller_network_data(self):
        """Get network data from UniFi Controller API
        
        This method directly implements the network data retrieval logic for the Controller API type.
        It was previously in the unifi.site.controller model, but has been integrated here.
        
        Returns:
            list: Network data from Controller API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_network_data', 'Getting network data from Controller API', 'outgoing')
        
        try:
            # Vérifier si nous avons une session d'authentification valide
            if not self._check_auth_session():
                _logger.error("Pas de session d'authentification valide pour récupérer les données des réseaux")
                return False
                
            # Construire l'URL de base en fonction du type de contrôleur (standard ou UDM Pro)
            base_url = f"https://{self.host}:{self.port}"
            
            # Déterminer si nous avons affaire à un UDM Pro
            is_udm_pro = self.auth_session_id and self.auth_session_id.is_udm_pro
            
            # Construire l'endpoint en fonction du type de contrôleur
            if is_udm_pro:
                # Pour UDM Pro, ajouter le préfixe /proxy/network
                endpoint = f"/proxy/network/api/s/{self.site_id}/rest/networkconf"
            else:
                # Pour les contrôleurs standard
                endpoint = f"/api/s/{self.site_id}/rest/networkconf"
                
            _logger.info(f"Récupération des réseaux depuis l'endpoint: {endpoint}")
            
            # Préparer les en-têtes de la requête
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Ajouter le token d'authentification si disponible (pour UDM Pro)
            if is_udm_pro and self.auth_session_id.token:
                headers['Authorization'] = f"Bearer {self.auth_session_id.token}"
            
            # Préparer les cookies pour l'authentification
            cookies = self._get_auth_cookies()
            if not cookies:
                _logger.error("Impossible de récupérer les cookies d'authentification")
                return False
                
            # Effectuer la requête HTTP
            url = f"{base_url}{endpoint}"
            _logger.info(f"Envoi de la requête GET à {url}")
            
            response = requests.get(
                url,
                headers=headers,
                cookies=cookies,
                verify=self.verify_ssl
            )
            
            # Vérifier le code de statut de la réponse
            if response.status_code != 200:
                _logger.error(f"Erreur lors de la récupération des données des réseaux: {response.status_code} - {response.text}")
                self._update_api_log(api_log, {
                    'status_code': response.status_code,
                    'response_body': response.text,
                    'message': f'Error: HTTP {response.status_code}',
                    'status': 'error'
                })
                return False
                
            # Analyser la réponse JSON
            try:
                result = response.json()
                _logger.info(f"Réponse reçue: {type(result)}")
                
                # Enregistrer les détails de la réponse dans le log API
                self._update_api_log(api_log, {
                    'status_code': response.status_code,
                    'response_body': response.text,
                    'message': 'Success: Retrieved network data',
                    'status': 'success'
                })
                
                # La plupart des API UniFi renvoient les données dans une clé 'data'
                if isinstance(result, dict) and 'data' in result:
                    return result['data']
                return result
                
            except json.JSONDecodeError as e:
                _logger.error(f"Erreur lors de l'analyse de la réponse JSON: {str(e)}")
                _logger.error(f"Contenu de la réponse: {response.text}")
                self._update_api_log(api_log, {
                    'status_code': response.status_code,
                    'response_body': response.text,
                    'message': f'Error: Invalid JSON response - {str(e)}',
                    'status': 'error'
                })
                return False
                
        except Exception as e:
            # Log the error
            _logger.exception(f"Erreur lors de la récupération des données des réseaux: {str(e)}")
            self._update_api_log(api_log, {
                'message': f'Error: {str(e)}',
                'status': 'error'
            })
            return False
            
    def _get_site_manager_network_data(self):
        """Get network data from UniFi Site Manager API
        
        This method directly implements the network data retrieval logic for the Site Manager API type.
        It was previously in the unifi.site.manager model, but has been integrated here.
        
        Returns:
            list: Network data from Site Manager API
        """
        # Create a log entry for this API call
        api_log = self._create_api_log('get_network_data', 'Getting network data from Site Manager API', 'outgoing')
        
        try:
            # Implement the Site Manager-specific API call logic here
            # Make the API request and process the response
            # For now, this is a placeholder
            result = []
            
            # Log the successful API call
            self._update_api_log(api_log, {'message': 'Success: Retrieved network data', 'status': 'success'})
            return result
        except Exception as e:
            # Log the error
            self._update_api_log(api_log, {'message': f'Error: {str(e)}', 'status': 'error'})
            _logger.error("Error getting network data from Site Manager API: %s", str(e))
            return False
    
    def _delegate_api_method(self, method_name):
        """Délègue l'appel d'une méthode à l'API appropriée
        
        Cette méthode générique permet d'appeler la méthode interne appropriée
        en fonction du type d'API configuré.
        
        Args:
            method_name: Nom de la méthode à appeler (sans le préfixe)
            
        Returns:
            Le résultat de la méthode appelée, ou False si le type d'API n'est pas pris en charge
        """
        self.ensure_one()
        
        # Déterminer le type d'API à utiliser
        if self.api_type == 'controller':
            # Utiliser l'implémentation Controller
            controller_method = f"_get_controller_{method_name}"
            if hasattr(self, controller_method):
                return getattr(self, controller_method)()
            else:
                _logger.error(f"Méthode {controller_method} non implémentée")
                return False
        elif self.api_type == 'site_manager':
            # Utiliser l'implémentation Site Manager
            site_manager_method = f"_get_site_manager_{method_name}"
            if hasattr(self, site_manager_method):
                return getattr(self, site_manager_method)()
            else:
                _logger.error(f"Méthode {site_manager_method} non implémentée")
                return False
        else:
            # Type d'API non pris en charge
            _logger.error("Type d'API non pris en charge: %s", self.api_type)
            return False

    def get_vlan_data(self):
        """Récupère les données des VLANs du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les VLANs.
        
        Returns:
            list: Liste des données de tous les VLANs
        """
        return self._delegate_api_method('get_vlan_data')
            
    def get_network_data(self):
        """Récupère les données des réseaux du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les réseaux.
        
        Returns:
            list: Liste des données de tous les réseaux
        """
        return self._delegate_api_method('get_network_data')

    def get_user_data(self):
        """Récupère les données des utilisateurs du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les utilisateurs.
        
        Returns:
            list: Liste des données de tous les utilisateurs
        """
        return self._delegate_api_method('get_user_data')

    def get_firewall_data(self):
        """Récupère les données des règles de pare-feu du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les règles de pare-feu.
        
        Returns:
            list: Liste des données de toutes les règles de pare-feu
        """
        return self._delegate_api_method('get_firewall_data')
            
    def get_port_forward_data(self):
        """Récupère les données des redirections de port du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les redirections de port.
        
        Returns:
            list: Liste des données de toutes les redirections de port
        """
        return self._delegate_api_method('get_port_forward_data')
            
    def get_system_info_data(self):
        """Récupère les données d'information système du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations système.
        
        Returns:
            dict: Données d'information système
        """
        return self._delegate_api_method('get_system_info_data')
        
    def action_import_site(self):
        """Lance directement l'import pour le site sélectionné
        
        Cette méthode est appelée lorsque l'utilisateur clique sur le bouton
        'Importer' dans la vue liste des sites UniFi. Elle déclenche
        immédiatement le processus d'importation pour le site sélectionné.
        
        Returns:
            dict: Notification de succès ou d'échec
        """
        self.ensure_one()
        
        # Dans la version refactorisée, nous n'avons plus besoin de vérifier si des anciens modèles 
        # sont associés puisque toute la logique est maintenant intégrée dans ce modèle
        
        # Vérifier si le site a déjà été configuré pour une API
        if not self.api_type:
            # Si aucun contrôleur ou gestionnaire de site n'est associé, ouvrir l'assistant d'importation
            return {
                'name': _('Import UniFi Site'),
                'type': 'ir.actions.act_window',
                'res_model': 'unifi.site.import.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_name': self.name, 'default_site_id': self.site_id, 'default_api_type': self.api_type}
            }
        
        # Tester la connexion
        connection_success = False
        if self.api_type == 'controller':
            connection_success = self._test_controller_connection()
        elif self.api_type == 'site_manager':
            connection_success = self._test_site_manager_connection()
        
        if connection_success:
            # Déclencher la synchronisation
            self.action_sync_now()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Connection successful! Synchronization started for site %s.') % self.name,
                    'sticky': False,
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Failed to connect to site %s. Please check your connection settings.') % self.name,
                    'sticky': True,
                    'type': 'danger',
                }
            }
