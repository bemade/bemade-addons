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
    controller_type = fields.Selection(
        selection=[
            ('standard', 'Standard Controller'),
            ('udm', 'UDM Pro / UCG Max')
        ],
        string='Controller Type',
        default='standard',
        help='Type of UniFi controller (affects API endpoints)'
    )
    
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
    
    # Relations avec d'autres modèles
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
    
    def action_sync_networks(self):
        """Synchronize networks from UniFi to Odoo
        
        This method fetches the latest network data from UniFi and updates
        the corresponding records in Odoo.
        
        Returns:
            dict: Action to reload the view
        """
        self.ensure_one()
        self._sync_networks()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    
    # Relations pour la configuration DNS
    dns_config_ids = fields.One2many(
        comodel_name='unifi.dns.config',
        inverse_name='site_id',
        string='DNS Configurations',
        help='DNS configurations for this site'
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
    
    # Champ pour le nombre de clients connectés
    client_count = fields.Integer(
        string='Connected Clients',
        compute='_compute_client_count',
        compute_sudo=True,
        store=False,
        help='Number of clients currently connected to this site'
    )
    
    # Champs pour les données brutes
    raw_data = fields.Text(
        string='Raw Data',
        help='Raw data from the API in JSON format',
        copy=False
    )
    
    raw_data_json = fields.Text(
        string='Raw Data JSON',
        help='Formatted JSON data for display',
        compute='_compute_raw_data_json',
        store=False
    )
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
    
    @api.depends('raw_data')
    def _compute_raw_data_json(self):
        """Format the raw data as JSON for display
        
        This method takes the raw data from the API and formats it as JSON
        for display in the UI.
        """
        for site in self:
            if site.raw_data:
                try:
                    # Try to parse and pretty-print the JSON
                    import json
                    data = json.loads(site.raw_data)
                    site.raw_data_json = json.dumps(data, indent=4, sort_keys=True)
                except Exception as e:
                    _logger.error('Error formatting raw data as JSON for site %s: %s', site.name, str(e))
                    site.raw_data_json = site.raw_data
            else:
                site.raw_data_json = False
    
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
    
    @api.depends('api_config_id', 'api_type')
    @api.depends('api_config_id', 'api_type')
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
    
    @api.depends('ssl_cert_file', 'ssl_cert_filename')
    def _compute_ssl_cert_path(self):
        """Compute the path to the SSL certificate file
        
        This method creates a temporary file with the SSL certificate content
        and sets the ssl_cert_path field to the path of this file.
        """
        for record in self:
            if record.ssl_cert_file and record.ssl_cert_filename:
                # Créer un fichier temporaire pour le certificat
                try:
                    # Créer un répertoire temporaire s'il n'existe pas
                    temp_dir = tempfile.gettempdir()
                    cert_dir = os.path.join(temp_dir, 'unifi_certs')
                    os.makedirs(cert_dir, exist_ok=True)
                    
                    # Créer le fichier de certificat
                    cert_path = os.path.join(cert_dir, record.ssl_cert_filename)
                    with open(cert_path, 'wb') as f:
                        f.write(base64.b64decode(record.ssl_cert_file))
                    
                    # Définir le chemin du certificat
                    record.ssl_cert_path = cert_path
                except Exception as e:
                    _logger.error("Error creating SSL certificate file: %s", str(e))
                    record.ssl_cert_path = False
            else:
                record.ssl_cert_path = False
    
    def test_connection(self):
        """Test connection to the UniFi site
        
        This method tests the connection to the UniFi site using the appropriate API.
        
        Returns:
            dict: Dictionary with connection test results
        """
        self.ensure_one()
        
        # Create an API log entry
        api_log = self.env['unifi.api.log'].create({
            'site_id': self.id,
            'api_method': 'test_connection',
            'message': _("Testing connection to UniFi site"),
            'direction': 'outbound',
            'status': 'pending',
        })
        
        # Test connection based on API type
        if self.api_type == 'controller':
            return self._test_controller_connection(api_log)
        elif self.api_type == 'site_manager':
            return self._test_site_manager_connection(api_log)
        else:
            # Update the API log
            self._update_api_log(api_log, {
                'status': 'error',
                'message': _("Unknown API type: %s") % self.api_type,
            })
            
            # Return failure
            return {
                'success': False,
                'message': _("Unknown API type: %s") % self.api_type,
                'details': {},
            }
    
    def _test_controller_connection(self, api_log=None):
        """Test connection to the UniFi Controller
        
        Args:
            api_log: Optional API log record to update with results
            
        Returns:
            dict: Dictionary with connection test results
        """
        # Delegate to the Controller API mixin
        controller_api = self.env['unifi.controller.api.mixin']
        return controller_api._test_controller_connection(self, api_log)
    
    def _test_site_manager_connection(self, api_log=None):
        """Test connection to the UniFi Site Manager API
        
        Args:
            api_log: Optional API log record to update with results
            
        Returns:
            dict: Dictionary with connection test results
        """
        # Delegate to the Site Manager API mixin
        site_manager_api = self.env['unifi.site.manager.api.mixin']
        return site_manager_api._test_site_manager_connection(self, api_log)
    
    def _update_api_log(self, api_log, values):
        """Update an API log record with the provided values
        
        Args:
            api_log: API log record to update
            values: Dictionary of values to update
            
        Returns:
            unifi.api.log: Updated API log record
        """
        if not api_log:
            return False
            
        try:
            # Update the API log
            api_log.write(values)
            return api_log
        except Exception as e:
            _logger.error("Error updating API log: %s", str(e))
            return False
    
    def _check_auth_session(self):
        """Check if the site has a valid authentication session
        
        Returns:
            bool: True if the site has a valid authentication session, False otherwise
        """
        self.ensure_one()
        
        # Check if we have an authentication session
        if not self.auth_session_id:
            return False
            
        # Check if the session is still valid
        if self.auth_session_id.is_expired:
            return False
            
        # Session is valid
        return True
    
    def _get_auth_cookies(self):
        """Get authentication cookies for the site
        
        Returns:
            dict: Dictionary of cookies or False if no valid session
        """
        self.ensure_one()
        
        # Check if we have a valid authentication session
        if not self._check_auth_session():
            return False
            
        # Get the cookies from the session
        cookies = {}
        if self.auth_session_id.cookies:
            try:
                cookies = ast.literal_eval(self.auth_session_id.cookies)
            except (ValueError, SyntaxError):
                _logger.error("Error parsing cookies: %s", self.auth_session_id.cookies)
                return False
                
        # Return the cookies
        return cookies
    
    def _create_auth_session(self, cookies, endpoint=None):
        """Create or update an authentication session for the site
        
        Args:
            cookies: Dictionary of cookies
            endpoint: Optional endpoint used for authentication
            
        Returns:
            unifi.auth.session: Created or updated authentication session
        """
        self.ensure_one()
        
        # Convert cookies to string
        cookies_str = str(cookies)
        
        # Check if we already have an authentication session
        if self.auth_session_id:
            # Update the existing session
            self.auth_session_id.write({
                'cookies': cookies_str,
                'last_used': fields.Datetime.now(),
                'is_expired': False,
                'endpoint': endpoint or self.auth_session_id.endpoint,
            })
            return self.auth_session_id
        else:
            # Create a new session
            session = self.env['unifi.auth.session'].create({
                'site_id': self.id,
                'cookies': cookies_str,
                'created': fields.Datetime.now(),
                'last_used': fields.Datetime.now(),
                'is_expired': False,
                'endpoint': endpoint,
            })
            
            # Update the site
            self.auth_session_id = session.id
            
            # Return the session
            return session
    
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
    
    # Méthodes refactorisées pour déléguer aux mixins
    
    def get_device_data(self):
        """Récupère les données des appareils du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les appareils.
        
        Returns:
            list: Liste des données de tous les appareils
        """
        self.ensure_one()
        
        # Delegate to the appropriate API mixin
        if self.api_type == 'controller':
            controller_api = self.env['unifi.controller.api.mixin']
            return controller_api._get_controller_device_data(self)
        elif self.api_type == 'site_manager':
            site_manager_api = self.env['unifi.site.manager.api.mixin']
            return site_manager_api._get_site_manager_device_data(self)
        else:
            return False
            
    def action_configure_controller(self):
        """Open a wizard to configure the Controller API settings
        
        This method is called from the UI to configure the Controller API settings.
        
        Returns:
            dict: Action to open the configuration wizard
        """
        self.ensure_one()
        return {
            'name': _('Configure Controller API'),
            'type': 'ir.actions.act_window',
            'res_model': 'unifi.site',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('unifi_integration.view_unifi_site_form').id,
            'target': 'new',
            'context': {'default_api_type': 'controller'}
        }
        
    def action_configure_site_manager(self):
        """Open a wizard to configure the Site Manager API settings
        
        This method is called from the UI to configure the Site Manager API settings.
        
        Returns:
            dict: Action to open the configuration wizard
        """
        self.ensure_one()
        return {
            'name': _('Configure Site Manager API'),
            'type': 'ir.actions.act_window',
            'res_model': 'unifi.site',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('unifi_integration.view_unifi_site_form').id,
            'target': 'new',
            'context': {'default_api_type': 'site_manager'}
        }
        
    def action_test_connection(self):
        """Test the connection to the UniFi site and import if successful
        
        This method is called from the UI to test the connection to the UniFi site
        and import the site if the connection is successful.
        
        Returns:
            dict: Action to open the site form or a notification of failure
        """
        self.ensure_one()
        
        # Test the connection
        result = self.test_connection()
        
        if result.get('success'):
            # Update the site status
            self.write({
                'import_status': 'success',
                'last_import_date': fields.Datetime.now()
            })
            
            # Return an action to open the site form
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'unifi.site',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'current',
                'context': {'form_view_initial_mode': 'edit'}
            }
        else:
            # Update the site status
            self.write({
                'import_status': 'failed'
            })
            
            # Return a notification of failure
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': result.get('message', _('Failed to connect to the UniFi site.')),
                    'sticky': True,
                    'type': 'danger'
                }
            }
    
    def _sync_networks(self):
        """Synchronize networks from UniFi to Odoo

        This method fetches the latest network data from UniFi and updates
        the corresponding records in Odoo.
        """
        self.ensure_one()
        try:
            # Vérifier si nous avons une session d'authentification valide
            if not self._check_auth_session():
                _logger.debug("Pas de session d'authentification valide pour le site %s, tentative d'authentification", self.name)
                # S'authentifier en fonction du type d'API
                if self.api_type == 'controller':
                    # Créer un log d'API pour l'authentification
                    api_log = self._create_api_log(
                        api_method='authenticate_controller',
                        message_text=_("Authenticating to UniFi Controller"),
                        direction='outbound'
                    )
                    
                    # Utiliser le mixin du contrôleur pour tester la connexion (qui authentifie aussi)
                    controller_api = self.env['unifi.controller.api.mixin']
                    auth_result = controller_api._test_controller_connection(self, api_log)
                    
                    if not auth_result.get('success', False):
                        _logger.error("Échec de l'authentification au contrôleur pour le site %s: %s", 
                                     self.name, auth_result.get('message', 'Unknown error'))
                        return False
                elif self.api_type == 'site_manager':
                    # Créer un log d'API pour l'authentification
                    api_log = self._create_api_log(
                        api_method='authenticate_site_manager',
                        message_text=_("Authenticating to UniFi Site Manager"),
                        direction='outbound'
                    )
                    
                    # Utiliser le mixin du site manager pour tester la connexion (qui authentifie aussi)
                    site_manager_api = self.env['unifi.site.manager.api.mixin']
                    auth_result = site_manager_api._test_site_manager_connection(self, api_log)
                    
                    if not auth_result.get('success', False):
                        _logger.error("Échec de l'authentification au site manager pour le site %s: %s", 
                                     self.name, auth_result.get('message', 'Unknown error'))
                        return False
                else:
                    _logger.error("Type d'API non pris en charge pour le site %s: %s", self.name, self.api_type)
                    return False
                
                _logger.debug("Authentification réussie pour le site %s", self.name)
            else:
                _logger.debug("Session d'authentification valide trouvée pour le site %s", self.name)
            
            # Récupérer les données des réseaux
            network_data = self.get_network_data()
            _logger.debug("Données de réseau récupérées pour le site %s: %s", self.name, network_data)
            
            if network_data:
                # Mettre à jour la date de dernière synchronisation
                self.write({
                    'last_sync': fields.Datetime.now(),
                    'last_update': fields.Datetime.now()
                })
                
                # Créer/mettre à jour les réseaux
                networks_created = 0
                for network in network_data:
                    self.env['unifi.network'].create_or_update_from_data(self, network)
                    networks_created += 1
                
                _logger.info("%d réseaux créés/mis à jour pour le site %s", networks_created, self.name)
                return True
            else:
                _logger.warning("Aucune donnée de réseau récupérée pour le site %s", self.name)
                return False
        except Exception as e:
            _logger.error("Error synchronizing networks for site %s: %s", self.name, str(e), exc_info=True)
            raise


    @api.model
    def action_sync_devices(self):
        """Synchronize devices from UniFi to Odoo
        
        This method fetches the latest device data from UniFi and updates
        the corresponding records in Odoo.
        
        Returns:
            dict: Action to reload the view
        """
        self.ensure_one()
        try:
            device_data = self.get_device_data()
            if device_data:
                self.write({
                    'last_sync': fields.Datetime.now(),
                    'last_update': fields.Datetime.now()
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Synchronisation'),
                    'message': _('Aucune donnée d\'appareil trouvée.'),
                    'type': 'warning',
                }
            }
        except Exception as e:
            _logger.error("Erreur lors de la synchronisation des appareils: %s", str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('Erreur lors de la synchronisation des appareils: %s') % str(e),
                    'type': 'danger',
                }
            }

    @api.model
    def action_sync_users(self):
        """Synchronize users from UniFi to Odoo
        
        This method fetches the latest user data from UniFi and updates
        the corresponding records in Odoo.
        
        Returns:
            dict: Action to reload the view
        """
        self.ensure_one()
        try:
            user_data = self.get_user_data()
            if user_data:
                self.write({
                    'last_sync': fields.Datetime.now(),
                    'last_update': fields.Datetime.now()
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Synchronisation'),
                    'message': _('Aucune donnée d\'utilisateur trouvée.'),
                    'type': 'warning',
                }
            }
        except Exception as e:
            _logger.error("Erreur lors de la synchronisation des utilisateurs: %s", str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('Erreur lors de la synchronisation des utilisateurs: %s') % str(e),
                    'type': 'danger',
                }
            }

    @api.model
    def action_sync_vlans(self):
        """Synchronize VLANs from UniFi to Odoo
        
        This method fetches the latest VLAN data from UniFi and updates
        the corresponding records in Odoo.
        
        Returns:
            dict: Action to reload the view
        """
        self.ensure_one()
        try:
            vlan_data = self.get_vlan_data()
            if vlan_data:
                self.write({
                    'last_sync': fields.Datetime.now(),
                    'last_update': fields.Datetime.now()
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Synchronisation'),
                    'message': _('Aucune donnée de VLAN trouvée.'),
                    'type': 'warning',
                }
            }
        except Exception as e:
            _logger.error("Erreur lors de la synchronisation des VLANs: %s", str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('Erreur lors de la synchronisation des VLANs: %s') % str(e),
                    'type': 'danger',
                }
            }

    @api.model
    def action_sync_firewall_rules(self):
        """Synchronize firewall rules from UniFi to Odoo
        
        This method fetches the latest firewall rule data from UniFi and updates
        the corresponding records in Odoo.
        
        Returns:
            dict: Action to reload the view
        """
        self.ensure_one()
        try:
            firewall_data = self.get_firewall_data()
            if firewall_data:
                self.write({
                    'last_sync': fields.Datetime.now(),
                    'last_update': fields.Datetime.now()
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Synchronisation'),
                    'message': _('Aucune donnée de règle de pare-feu trouvée.'),
                    'type': 'warning',
                }
            }
        except Exception as e:
            _logger.error("Erreur lors de la synchronisation des règles de pare-feu: %s", str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('Erreur lors de la synchronisation des règles de pare-feu: %s') % str(e),
                    'type': 'danger',
                }
            }

    @api.model
    def action_sync_port_forwards(self):
        """Synchronize port forwards from UniFi to Odoo
        
        This method fetches the latest port forward data from UniFi and updates
        the corresponding records in Odoo.
        
        Returns:
            dict: Action to reload the view
        """
        self.ensure_one()
        try:
            port_forward_data = self.get_port_forward_data()
            if port_forward_data:
                self.write({
                    'last_sync': fields.Datetime.now(),
                    'last_update': fields.Datetime.now()
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Synchronisation'),
                    'message': _('Aucune donnée de redirection de port trouvée.'),
                    'type': 'warning',
                }
            }
        except Exception as e:
            _logger.error("Erreur lors de la synchronisation des redirections de port: %s", str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('Erreur lors de la synchronisation des redirections de port: %s') % str(e),
                    'type': 'danger',
                }
            }

    @api.model
    def action_sync_system_info(self):
        """Synchronize system info from UniFi to Odoo
        
        This method fetches the latest system info data from UniFi and updates
        the corresponding records in Odoo.
        
        Returns:
            dict: Action to reload the view
        """
        self.ensure_one()
        try:
            system_info_data = self.get_system_info_data()
            if system_info_data:
                self.write({
                    'last_sync': fields.Datetime.now(),
                    'last_update': fields.Datetime.now()
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Synchronisation'),
                    'message': _('Aucune donnée système trouvée.'),
                    'type': 'warning',
                }
            }
        except Exception as e:
            _logger.error("Erreur lors de la synchronisation des informations système: %s", str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('Erreur lors de la synchronisation des informations système: %s') % str(e),
                    'type': 'danger',
                }
            }

    @api.model
    def action_sync_dns(self):
        """Synchronize DNS entries from UniFi to Odoo
        
        This method fetches the latest DNS data from UniFi and updates
        the corresponding records in Odoo.
        
        Returns:
            dict: Action to reload the view
        """
        self.ensure_one()
        try:
            dns_data = self.get_dns_data()
            if dns_data:
                self.write({
                    'last_sync': fields.Datetime.now(),
                    'last_update': fields.Datetime.now()
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Synchronisation'),
                    'message': _('Aucune donnée DNS trouvée.'),
                    'type': 'warning',
                }
            }
        except Exception as e:
            _logger.error("Erreur lors de la synchronisation des entrées DNS: %s", str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('Erreur lors de la synchronisation des entrées DNS: %s') % str(e),
                    'type': 'danger',
                }
            }

    @api.model
    def action_sync_wifi(self):
        """Synchronize WiFi networks from UniFi to Odoo
        
        This method fetches the latest WiFi network data from UniFi and updates
        the corresponding records in Odoo.
        
        Returns:
            dict: Action to reload the view
        """
        self.ensure_one()
        try:
            wifi_data = self.get_wifi_data()
            if wifi_data:
                self.write({
                    'last_sync': fields.Datetime.now(),
                    'last_update': fields.Datetime.now()
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Synchronisation'),
                    'message': _('Aucune donnée de réseau WiFi trouvée.'),
                    'type': 'warning',
                }
            }
        except Exception as e:
            _logger.error("Erreur lors de la synchronisation des réseaux WiFi: %s", str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('Erreur lors de la synchronisation des réseaux WiFi: %s') % str(e),
                    'type': 'danger',
                }
            }

    @api.model
    def action_sync_routing(self):
        """Synchronize routing configurations from UniFi to Odoo
        
        This method fetches the latest routing configuration data from UniFi and updates
        the corresponding records in Odoo.
        
        Returns:
            dict: Action to reload the view
        """
        self.ensure_one()
        try:
            routing_data = self.get_routing_data()
            if routing_data:
                self.write({
                    'last_sync': fields.Datetime.now(),
                    'last_update': fields.Datetime.now()
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Synchronisation'),
                    'message': _('Aucune donnée de routage trouvée.'),
                    'type': 'warning',
                }
            }
        except Exception as e:
            _logger.error("Erreur lors de la synchronisation des configurations de routage: %s", str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('Erreur lors de la synchronisation des configurations de routage: %s') % str(e),
                    'type': 'danger',
                }
            }

    def get_network_data(self):
        """Récupère les données des réseaux du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les réseaux.
        
        Returns:
            list: Liste des données de tous les réseaux
        """
        self.ensure_one()
        
        _logger.debug("Début de get_network_data pour le site %s (type: %s)", self.name, self.api_type)
        
        # Delegate to the appropriate API mixin
        if self.api_type == 'controller':
            _logger.debug("Utilisation de l'API Controller pour récupérer les réseaux")
            controller_api = self.env['unifi.controller.api.mixin']
            data = controller_api._get_controller_network_data(self)
            _logger.debug("Données récupérées depuis l'API Controller: %s", data)
            return data
        elif self.api_type == 'site_manager':
            _logger.debug("Utilisation de l'API Site Manager pour récupérer les réseaux")
            site_manager_api = self.env['unifi.site.manager.api.mixin']
            data = site_manager_api._get_site_manager_network_data(self)
            _logger.debug("Données récupérées depuis l'API Site Manager: %s", data)
            return data
        else:
            _logger.debug("Type d'API non reconnu: %s", self.api_type)
            return False
            
    def get_dns_data(self):
        """Récupère les données DNS du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations DNS.
        
        Returns:
            list: Liste des données DNS
        """
        self.ensure_one()
        
        # Delegate to the appropriate API mixin
        if self.api_type == 'controller':
            controller_api = self.env['unifi.controller.api.mixin']
            return controller_api._get_controller_dns_data(self)
        elif self.api_type == 'site_manager':
            site_manager_api = self.env['unifi.site.manager.api.mixin']
            return site_manager_api._get_site_manager_dns_data(self)
        else:
            return False
            
    def get_wifi_data(self):
        """Récupère les données des réseaux WiFi du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les réseaux WiFi.
        
        Returns:
            list: Liste des données des réseaux WiFi
        """
        self.ensure_one()
        
        # Delegate to the appropriate API mixin
        if self.api_type == 'controller':
            controller_api = self.env['unifi.controller.api.mixin']
            return controller_api._get_controller_wifi_data(self)
        elif self.api_type == 'site_manager':
            site_manager_api = self.env['unifi.site.manager.api.mixin']
            return site_manager_api._get_site_manager_wifi_data(self)
        else:
            return False
            
    def get_routing_data(self):
        """Récupère les données de routage du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations de routage.
        
        Returns:
            list: Liste des données de routage
        """
        self.ensure_one()
        
        # Delegate to the appropriate API mixin
        if self.api_type == 'controller':
            controller_api = self.env['unifi.controller.api.mixin']
            return controller_api._get_controller_routing_data(self)
        elif self.api_type == 'site_manager':
            site_manager_api = self.env['unifi.site.manager.api.mixin']
            return site_manager_api._get_site_manager_routing_data(self)
        else:
            return False
        """Récupère les données des réseaux du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les réseaux.
        
        Returns:
            list: Liste des données de tous les réseaux
        """
        self.ensure_one()
        
        # Delegate to the appropriate API mixin
        if self.api_type == 'controller':
            controller_api = self.env['unifi.controller.api.mixin']
            return controller_api._get_controller_network_data(self)
        elif self.api_type == 'site_manager':
            site_manager_api = self.env['unifi.site.manager.api.mixin']
            return site_manager_api._get_site_manager_network_data(self)
        else:
            return False
    
    def get_vlan_data(self):
        """Récupère les données des VLANs du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les VLANs.
        
        Returns:
            list: Liste des données de tous les VLANs
        """
        self.ensure_one()
        
        # Delegate to the appropriate API mixin
        if self.api_type == 'controller':
            controller_api = self.env['unifi.controller.api.mixin']
            return controller_api._get_controller_vlan_data(self)
        elif self.api_type == 'site_manager':
            site_manager_api = self.env['unifi.site.manager.api.mixin']
            return site_manager_api._get_site_manager_vlan_data(self)
        else:
            return False
    
    def get_user_data(self):
        """Récupère les données des utilisateurs du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les utilisateurs.
        
        Returns:
            list: Liste des données de tous les utilisateurs
        """
        self.ensure_one()
        
        # Delegate to the appropriate API mixin
        if self.api_type == 'controller':
            controller_api = self.env['unifi.controller.api.mixin']
            return controller_api._get_controller_user_data(self)
        elif self.api_type == 'site_manager':
            site_manager_api = self.env['unifi.site.manager.api.mixin']
            return site_manager_api._get_site_manager_user_data(self)
        else:
            return False
    
    def get_firewall_data(self):
        """Récupère les données des règles de pare-feu du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les règles de pare-feu.
        
        Returns:
            list: Liste des données de toutes les règles de pare-feu
        """
        self.ensure_one()
        
        # Delegate to the appropriate API mixin
        if self.api_type == 'controller':
            controller_api = self.env['unifi.controller.api.mixin']
            return controller_api._get_controller_firewall_data(self)
        elif self.api_type == 'site_manager':
            site_manager_api = self.env['unifi.site.manager.api.mixin']
            return site_manager_api._get_site_manager_firewall_data(self)
        else:
            return False
    
    def get_port_forward_data(self):
        """Récupère les données des redirections de port du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les redirections de port.
        
        Returns:
            list: Liste des données de toutes les redirections de port
        """
        self.ensure_one()
        
        # Delegate to the appropriate API mixin
        if self.api_type == 'controller':
            controller_api = self.env['unifi.controller.api.mixin']
            return controller_api._get_controller_port_forward_data(self)
        elif self.api_type == 'site_manager':
            site_manager_api = self.env['unifi.site.manager.api.mixin']
            return site_manager_api._get_site_manager_port_forward_data(self)
        else:
            return False
    
    def get_system_info_data(self):
        """Récupère les données d'information système du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations système.
        
        Returns:
            list: Liste des données d'information système
        """
        self.ensure_one()
        
        # Delegate to the appropriate API mixin
        if self.api_type == 'controller':
            controller_api = self.env['unifi.controller.api.mixin']
            return controller_api._get_controller_system_info_data(self)
        elif self.api_type == 'site_manager':
            site_manager_api = self.env['unifi.site.manager.api.mixin']
            return site_manager_api._get_site_manager_system_info_data(self)
        else:
            return False
    
    def action_sync_now(self):
        """Action to synchronize the site now
        
        This method is called from the UI to synchronize the site immediately.
        
        Returns:
            dict: Dictionary with action result
        """
        self.ensure_one()
        
        # Synchronize the site
        if self.api_type == 'controller':
            controller_api = self.env['unifi.controller.api.mixin']
            result = controller_api._sync_controller(self)
        elif self.api_type == 'site_manager':
            site_manager_api = self.env['unifi.site.manager.api.mixin']
            result = site_manager_api._sync_site_manager(self)
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Synchronization"),
                    'message': _("Unknown API type: %s") % self.api_type,
                    'sticky': True,
                    'type': 'danger',
                    'next': {
                        'type': 'ir.actions.act_window_close',
                    },
                },
            }
        
        # Show a notification with the result
        if result['success']:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Synchronization"),
                    'message': result['message'],
                    'sticky': False,
                    'type': 'success',
                    'next': {
                        'type': 'ir.actions.act_window_close',
                    },
                },
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Synchronization"),
                    'message': result['message'],
                    'sticky': True,
                    'type': 'danger',
                    'next': {
                        'type': 'ir.actions.act_window_close',
                    },
                },
            }
            
    def action_import_site(self):
        """Lance directement l'import pour le site sélectionné
        
        Cette méthode est appelée lorsque l'utilisateur clique sur le bouton
        'Importer' dans la vue liste des sites UniFi. Elle déclenche
        immédiatement le processus d'importation pour le site sélectionné.
        
        Returns:
            dict: Notification de succès ou d'échec
        """
        self.ensure_one()
        
        # Vérifier si le site a déjà été configuré pour une API
        if not self.api_type:
            # Si aucun type d'API n'est défini, ouvrir l'assistant d'importation
            return {
                'name': _('Import UniFi Site'),
                'type': 'ir.actions.act_window',
                'res_model': 'unifi.site.import.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_name': self.name, 'default_site_id': self.site_id, 'default_api_type': self.api_type}
            }
            
    # Action methods for viewing related records
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
            'res_model': 'unifi.port.forward',
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
        
        # Tester la connexion
        connection_test = self.test_connection()
        connection_success = connection_test.get('success', False)
        
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