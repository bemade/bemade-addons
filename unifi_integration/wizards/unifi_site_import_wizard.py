# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import urllib3
from requests.exceptions import RequestException, ConnectionError
import json
import logging

_logger = logging.getLogger(__name__)


class UnifiSiteImportWizard(models.TransientModel):
    """Wizard to create a new UniFi site with multi-step process"""
    _name = 'unifi.site.import.wizard'
    _description = 'Import UniFi Site Wizard'

    # Common fields
    name = fields.Char(
        string='Site Name',
        required=True
    )

    api_type = fields.Selection(
        selection=[
            ('controller', 'UniFi Controller (Local)'),
            ('site_manager', 'UniFi Site Manager (Cloud)')
        ],
        string='API Type',
        required=True,
        default='controller'
    )
    
    # State management
    state = fields.Selection(
        selection=[
            ('api_selection', 'API Selection'),
            ('controller_config', 'Controller Configuration'),
            ('site_manager_config', 'Site Manager Configuration'),
            ('mfa_verification', 'MFA Verification'),
            ('site_discovery', 'Site Discovery'),
            ('review', 'Review')
        ],
        default='api_selection',
        string='Wizard State'
    )
    
    # Controller API fields
    host = fields.Char(
        string='Controller IP/Hostname'
    )

    port = fields.Integer(
        string='Port',
        default=443
    )

    username = fields.Char(
        string='Username'
    )

    password = fields.Char(
        string='Password'
    )

    site_id = fields.Char(
        string='Site ID',
        default='default',
        help="Site identifier in UniFi (usually 'default' unless configured otherwise)"
    )

    controller_type = fields.Selection(
        selection=[
            ('udm', 'UniFi Dream Machine (UDM/UDM Pro)'),
            ('controller', 'UniFi Network Controller')
        ],
        string='Controller Type',
        default='udm'
    )
    
    # Site Manager API fields
    api_key = fields.Char(
        string='API Key'
    )

    mfa_enabled = fields.Boolean(
        string='MFA Enabled',
        default=False
    )
    mfa_code = fields.Char(
        string='MFA Code'
    )
    
    # Site Discovery fields
    discovered_site_ids = fields.Many2many(
        comodel_name='unifi.site.discovery',
        string='Discovered Sites'
    )
    
    selected_site_id = fields.Many2one(
        comodel_name='unifi.site.discovery',
        string='Selected Site'
    )
    
    # Review fields
    summary = fields.Text(
        string='Summary',
        readonly=True
    )
    
    @api.onchange('api_type')
    def _onchange_api_type(self):
        """Update state based on API type selection"""
        if self.api_type == 'controller':
            self.state = 'controller_config'
        elif self.api_type == 'site_manager':
            self.state = 'site_manager_config'
    
    def action_next(self):
        """Move to the next step in the wizard"""
        self.ensure_one()
        
        if self.state == 'api_selection':
            if self.api_type == 'controller':
                self.state = 'controller_config'
            else:
                self.state = 'site_manager_config'
        
        elif self.state == 'controller_config':
            # Validate controller connection
            if not self._validate_controller_connection():
                return self._reopen_view()
            self.state = 'site_discovery'
            self._discover_sites()
        
        elif self.state == 'site_manager_config':
            # Validate site manager connection
            if not self._validate_site_manager_connection():
                return self._reopen_view()
            
            if self.mfa_enabled:
                self.state = 'mfa_verification'
            else:
                self.state = 'site_discovery'
                self._discover_sites()
        
        elif self.state == 'mfa_verification':
            # Validate MFA code
            if not self._validate_mfa_code():
                return self._reopen_view()
            self.state = 'site_discovery'
            self._discover_sites()
        
        elif self.state == 'site_discovery':
            if not self.selected_site_id:
                raise UserError(_('Please select a site to import'))
            self.state = 'review'
            self._prepare_summary()
        
        return self._reopen_view()
    
    def action_previous(self):
        """Move to the previous step in the wizard"""
        self.ensure_one()
        
        if self.state == 'controller_config' or self.state == 'site_manager_config':
            self.state = 'api_selection'
        
        elif self.state == 'mfa_verification':
            self.state = 'site_manager_config'
        
        elif self.state == 'site_discovery':
            if self.api_type == 'controller':
                self.state = 'controller_config'
            elif self.mfa_enabled:
                self.state = 'mfa_verification'
            else:
                self.state = 'site_manager_config'
        
        elif self.state == 'review':
            self.state = 'site_discovery'
        
        return self._reopen_view()
    
    def _reopen_view(self):
        """Reopen the wizard view with the current state"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_test_connection(self):
        """Test connection to the UniFi site
        
        This method is called when the user clicks the 'Test Connection' button
        in the wizard. It delegates to the appropriate validation method based on
        the selected API type.
        
        If the connection is successful, it will automatically create the site.
        
        Returns:
            dict: Action to reopen the wizard with a success or error message
        """
        self.ensure_one()
        
        # Validation des champs requis
        if not self.name or not self.site_id or not self.api_type:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Missing Information'),
                    'message': _('Please fill in all required fields: Name, Site ID, and API Type'),
                    'sticky': False,
                    'type': 'warning',
                }
            }
        
        try:
            connection_success = False
            
            if self.api_type == 'controller':
                if self._validate_controller_connection():
                    connection_success = True
                    message = _('Successfully connected to the UniFi Controller')
            elif self.api_type == 'site_manager':
                if self._validate_site_manager_connection():
                    connection_success = True
                    message = _('Successfully connected to the UniFi Site Manager')
            
            if connection_success:
                # Créer le site automatiquement
                site_vals = {
                    'name': self.name,
                    'site_id': self.site_id,
                    'api_type': self.api_type,
                    'active': True,
                }
                
                # Créer d'abord le site principal
                site = self.env['unifi.site'].create(site_vals)
                
                # Ensuite, créer l'enregistrement spécifique au type d'API
                if self.api_type == 'controller':
                    # Créer un enregistrement unifi.site.controller
                    controller_vals = {
                        'site_id': site.id,
                        'host': self.host,
                        'port': self.port,
                        'username': self.username,
                        'password': self.password,
                        'controller_type': self.controller_type,
                    }
                    self.env['unifi.site.controller'].create(controller_vals)
                    _logger.info("Created controller record for site %s", site.name)
                else:
                    # Créer un enregistrement unifi.site.manager
                    manager_vals = {
                        'site_id': site.id,
                        'api_key': self.api_key,
                        'mfa_enabled': self.mfa_enabled,
                    }
                    self.env['unifi.site.manager'].create(manager_vals)
                    _logger.info("Created site manager record for site %s", site.name)
                
                # Afficher un message de succès et rediriger vers le site créé
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Site %s created successfully!') % self.name,
                        'sticky': False,
                        'type': 'success',
                        'next': {
                            'type': 'ir.actions.act_window',
                            'name': _('Site'),
                            'res_model': 'unifi.site',
                            'res_id': site.id,
                            'view_mode': 'form',
                            'target': 'current',
                        },
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': str(e),
                    'sticky': False,
                    'type': 'danger',
                }
            }
        
        return self._reopen_view()
    
    def _validate_controller_connection(self):
        """Test connection to the UniFi Controller"""
        if not self.host or not self.port or not self.username or not self.password:
            raise UserError(_('All controller connection fields are required'))
        
        try:
            # Disable SSL verification warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Log connection attempt
            _logger.info("Attempting to connect to UniFi Controller at %s:%s with username %s", 
                        self.host, self.port, self.username)
            
            # Nettoyer l'URL du host (enlever https:// ou http:// s'il est déjà présent)
            host = self.host
            if host.startswith('https://'):
                host = host[8:]
            elif host.startswith('http://'):
                host = host[7:]
            
            # Determine login URL based on controller type
            if self.controller_type == 'udm':
                # For UDM/UDM Pro
                login_url = f'https://{host}:{self.port}/api/auth/login'
            else:
                # For older controllers
                login_url = f'https://{host}:{self.port}/api/login'
            
            _logger.info("Using login URL: %s", login_url)
            
            login_data = {
                'username': self.username,
                'password': self.password
            }
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            # Increase timeout for slow connections
            _logger.info("Sending login request...")
            response = requests.post(
                login_url,
                json=login_data,
                headers=headers,
                verify=False,
                timeout=30  # Increased timeout
            )
            
            _logger.info("Login response status code: %s", response.status_code)
            
            # Log response details for debugging
            if response.status_code != 200:
                _logger.error("Login failed with status code %s: %s", 
                             response.status_code, response.text)
                raise UserError(_('Failed to authenticate with UniFi Controller: HTTP %s - %s') 
                              % (response.status_code, response.text))
            
            # Check response content
            response_data = response.json()
            _logger.info("Login successful, response data: %s", response_data)
            
            return True
        
        except ConnectionError as e:
            _logger.error("Connection error: %s", str(e))
            raise UserError(_('Failed to connect to UniFi Controller: %s') % str(e))
        except RequestException as e:
            _logger.error("Request exception: %s", str(e))
            raise UserError(_('Failed to authenticate with UniFi Controller: %s') % str(e))
        except ValueError as e:
            _logger.error("JSON parsing error: %s", str(e))
            raise UserError(_('Invalid response from UniFi Controller: %s') % str(e))
        except Exception as e:
            _logger.error("Unexpected error: %s", str(e), exc_info=True)
            raise UserError(_('Unexpected error: %s') % str(e))
    
    def _validate_site_manager_connection(self):
        """Test connection to the UniFi Site Manager API"""
        if not self.api_key:
            raise UserError(_('API Key is required for Site Manager connection'))
        
        try:
            # Test connection to Site Manager API
            headers = {
                'Accept': 'application/json',
                'x-auth-token': self.api_key
            }
            
            response = requests.get(
                'https://api.ui.com/me',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('mfa_required', False):
                    self.mfa_enabled = True
                return True
            else:
                raise UserError(_('Failed to authenticate with Site Manager API: %s') % response.text)
        
        except ConnectionError as e:
            raise UserError(_('Failed to connect to Site Manager API: %s') % str(e))
        except RequestException as e:
            raise UserError(_('Failed to authenticate with Site Manager API: %s') % str(e))
        except Exception as e:
            raise UserError(_('Unexpected error: %s') % str(e))
    
    def _validate_mfa_code(self):
        """Validate the MFA code for Site Manager API"""
        if not self.mfa_code:
            raise UserError(_('MFA Code is required'))
        
        try:
            # Validate MFA code
            headers = {
                'Accept': 'application/json',
                'x-auth-token': self.api_key
            }
            
            response = requests.post(
                'https://api.ui.com/api/auth/mfa',
                headers=headers,
                json={'code': self.mfa_code},
                timeout=10
            )
            
            if response.status_code == 200:
                # Update API key with the new token that includes MFA verification
                data = response.json()
                if 'token' in data:
                    self.api_key = data['token']
                return True
            else:
                raise UserError(_('Invalid MFA code: %s') % response.text)
        
        except ConnectionError as e:
            raise UserError(_('Failed to connect to Site Manager API: %s') % str(e))
        except RequestException as e:
            raise UserError(_('Failed to validate MFA code: %s') % str(e))
        except Exception as e:
            raise UserError(_('Unexpected error: %s') % str(e))
    
    def _discover_sites(self):
        """Discover available sites from the selected API"""
        # This would be implemented to query the API and populate discovered_site_ids
        # For now, we'll create a placeholder
        self.env['unifi.site.discovery'].search([]).unlink()  # Clear previous discoveries
        
        if self.api_type == 'controller':
            self._discover_controller_sites()
        else:
            self._discover_site_manager_sites()
    
    def _get_selection_label(self, field_name, value):
        """Helper method to get the label for a selection field value"""
        if not field_name or not value:
            return ''
            
        # Utiliser des valeurs codées en dur pour les champs de sélection connus
        # Cette approche évite les problèmes d'accès aux attributs des champs
        selection_dict = {}
        
        if field_name == 'api_type':
            selection_dict = {
                'controller': 'Controller',
                'site_manager': 'Site Manager'
            }
        elif field_name == 'controller_type':
            selection_dict = {
                'udm': 'UniFi Dream Machine',
                'cloud_key': 'Cloud Key',
                'other': 'Other'
            }
        elif field_name == 'state':
            selection_dict = {
                'api_selection': 'API Selection',
                'controller_config': 'Controller Configuration',
                'site_manager_config': 'Site Manager Configuration',
                'site_discovery': 'Site Discovery',
                'site_selection': 'Site Selection',
                'review': 'Review',
                'done': 'Done'
            }
            
        return selection_dict.get(value, value)
        
    def _discover_controller_sites(self):
        """Discover sites from UniFi Controller"""
        try:
            # Validate required fields
            if not self.host or not self.port or not self.username or not self.password:
                raise UserError(_('Host, port, username, and password are required for controller connection'))
                
            # Disable SSL verification warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Login to Controller
            login_url = f'https://{self.host}:{self.port}/api/auth/login'
            login_data = {
                'username': self.username,
                'password': self.password
            }
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            _logger.info("Connecting to UniFi Controller at %s:%s", self.host, self.port)
            session = requests.Session()
            response = session.post(
                login_url,
                json=login_data,
                headers=headers,
                verify=False,
                timeout=10
            )
            response.raise_for_status()
            
            # Get sites
            sites_url = f'https://{self.host}:{self.port}/api/self/sites'
            _logger.info("Retrieving sites from UniFi Controller")
            response = session.get(
                sites_url,
                headers=headers,
                verify=False,
                timeout=10
            )
            response.raise_for_status()
            
            sites_data = response.json()
            discovered_sites = []
            
            # Safely extract data from the response
            sites_list = []
            if isinstance(sites_data, dict) and 'data' in sites_data and isinstance(sites_data['data'], list):
                sites_list = sites_data['data']
            
            if not sites_list:
                _logger.warning("No sites found in UniFi Controller response")
                return
                
            _logger.info("Found %d sites in UniFi Controller", len(sites_list))
            for site in sites_list:
                # Ensure site is a dictionary
                if not isinstance(site, dict):
                    continue
                    
                site_name = site.get('desc') if 'desc' in site else 'Unknown'
                site_id = site.get('name') if 'name' in site else 'default'
                _logger.info("Discovered site: %s (ID: %s)", site_name, site_id)
                
                # Convert site dict to JSON string for storage
                site_details = json.dumps(site)
                
                site_record = self.env['unifi.site.discovery'].create({
                    'name': site_name,
                    'site_id': site_id,
                    'api_type': 'controller',
                    'details': site_details
                })
                discovered_sites.append(site_record.id)
            
            self.discovered_site_ids = [(6, 0, discovered_sites)]
            
        except requests.exceptions.ConnectionError as e:
            _logger.error("Connection error to UniFi Controller: %s", str(e))
            raise UserError(_('Failed to connect to UniFi Controller: %s') % str(e))
        except requests.exceptions.HTTPError as e:
            _logger.error("HTTP error from UniFi Controller: %s", str(e))
            raise UserError(_('Failed to authenticate with UniFi Controller: %s') % str(e))
        except Exception as e:
            _logger.error("Error discovering controller sites: %s", str(e))
            raise UserError(_('Failed to discover sites: %s') % str(e))
    
    def _discover_site_manager_sites(self):
        """Discover sites from UniFi Site Manager"""
        try:
            # Validate required fields
            if not self.api_key:
                raise UserError(_('API Key is required for Site Manager connection'))
                
            # Get sites from Site Manager API
            headers = {
                'Accept': 'application/json',
                'x-auth-token': self.api_key
            }
            
            _logger.info("Connecting to UniFi Site Manager API")
            response = requests.get(
                'https://api.ui.com/api/sites',
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            sites_data = response.json()
            discovered_sites = []
            
            # Safely extract data from the response
            sites_list = []
            if isinstance(sites_data, dict) and 'data' in sites_data and isinstance(sites_data['data'], list):
                sites_list = sites_data['data']
            
            if not sites_list:
                _logger.warning("No sites found in UniFi Site Manager response")
                return
                
            _logger.info("Found %d sites in UniFi Site Manager", len(sites_list))
            for site in sites_list:
                # Ensure site is a dictionary
                if not isinstance(site, dict):
                    continue
                    
                site_name = site.get('name') if 'name' in site else 'Unknown'
                site_id = site.get('id') if 'id' in site else ''
                _logger.info("Discovered site: %s (ID: %s)", site_name, site_id)
                
                # Convert site dict to JSON string for storage
                site_details = json.dumps(site)
                
                site_record = self.env['unifi.site.discovery'].create({
                    'name': site_name,
                    'site_id': site_id,
                    'api_type': 'site_manager',
                    'details': site_details
                })
                discovered_sites.append(site_record.id)
            
            self.discovered_site_ids = [(6, 0, discovered_sites)]
            
        except requests.exceptions.ConnectionError as e:
            _logger.error("Connection error to UniFi Site Manager API: %s", str(e))
            raise UserError(_('Failed to connect to UniFi Site Manager API: %s') % str(e))
        except requests.exceptions.HTTPError as e:
            _logger.error("HTTP error from UniFi Site Manager API: %s", str(e))
            raise UserError(_('Failed to authenticate with UniFi Site Manager API: %s') % str(e))
        except Exception as e:
            _logger.error("Error discovering site manager sites: %s", str(e))
            raise UserError(_('Failed to discover sites: %s') % str(e))
    
    def _prepare_summary(self):
        """Prepare summary for review step"""
        # Vérifier si un site a été sélectionné
        if not self.selected_site_id or not isinstance(self.selected_site_id, models.Model):
            _logger.warning("No site selected or invalid site selection")
            return
            
        # Récupérer le site sélectionné
        site = self.selected_site_id
        
        # Créer le résumé avec les informations de base
        summary = _("""
Site Import Summary:

Name: {name}
API Type: {api_type}
Site ID: {site_id}
        """).format(
            name=self.name or '',
            api_type=self._get_selection_label('api_type', self.api_type),
            site_id=site.site_id if hasattr(site, 'site_id') else ''
        )
        
        if self.api_type == 'controller':
            summary += _("""
Controller Host: {host}
Controller Port: {port}
Controller Type: {controller_type}
            """).format(
                host=self.host,
                port=self.port,
                controller_type=self._get_selection_label('controller_type', self.controller_type)
            )
        else:
            summary += _("""
Site Manager API: Configured
MFA Enabled: {mfa_enabled}
            """).format(
                mfa_enabled=_('Yes') if self.mfa_enabled else _('No')
            )
        
        self.summary = summary
    
    def action_import_site(self):
        """Create a new site and configuration from the form data"""
        self.ensure_one()
        
        # Validation des champs requis
        if not self.name or not self.site_id or not self.api_type:
            raise UserError(_('Please fill in all required fields'))
            
        # Validation des champs spécifiques au type d'API
        if self.api_type == 'controller':
            if not self.host or not self.port or not self.username or not self.password:
                raise UserError(_('Please fill in all controller connection fields'))
        elif self.api_type == 'site_manager':
            if not self.api_key:
                raise UserError(_('Please provide your UniFi Site Manager API key'))
        
        try:
            # Create the site
            site_vals = {
                'name': self.name,
                'site_id': self.site_id,
                'api_type': self.api_type,
                'active': True,
            }
            
            if self.api_type == 'controller':
                site_vals.update({
                    'host': self.host,
                    'port': self.port,
                    'username': self.username,
                    'password': self.password,
                    'controller_type': self.controller_type,
                })
            else:
                site_vals.update({
                    'api_key': self.api_key,
                    'mfa_enabled': self.mfa_enabled,
                })
            
            site = self.env['unifi.site'].create(site_vals)
            
            # Afficher un message de succès
            message = _('Site %s created successfully!') % self.name
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': message,
                    'sticky': False,
                    'type': 'success',
                    'next': {
                        'type': 'ir.actions.act_window',
                        'name': _('Site'),
                        'res_model': 'unifi.site',
                        'res_id': site.id,
                        'view_mode': 'form',
                        'target': 'current',
                    },
                }
            }
            
        except Exception as e:
            raise UserError(_('Failed to create site: %s') % str(e))
