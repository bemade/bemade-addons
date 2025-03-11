# -*- coding: utf-8 -*-

# pylint: disable=import-error
from odoo import http, _  # IDE may report an error, but works in Odoo environment
from odoo.http import request  # IDE may report an error, but works in Odoo environment
# pylint: enable=import-error
import logging
import json  # Required to parse API responses and used in processing methods
import requests
from requests.exceptions import RequestException, ConnectionError
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from datetime import datetime

# Remove warnings for insecure connections
try:
    # For newer versions of requests
    import urllib3
    urllib3.disable_warnings(category=InsecureRequestWarning)
except ImportError:
    # For older versions of requests
    try:
        # Disable pylint security warning for this specific line
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except AttributeError:
        # If neither works, we silently ignore
        pass

_logger = logging.getLogger(__name__)

class UdmProController(http.Controller):
    """Controller for UDM Pro related functionalities in Odoo"""
    
    @http.route('/udm_pro/advanced_options', type='http', auth='user', website=True)
    def advanced_options_form(self):
        """Display the advanced options form for the UDM Pro API"""
        return request.render('unifi_integration.advanced_options_form', {
            'default_site': 'default',
            'fixed_only': True,
            'lowercase_hostnames': True,
        })
    
    @http.route('/udm_pro/restart_device', type='http', auth='user', website=True)
    def restart_device_form(self):
        """Display the form to restart a UDM Pro device"""
        if not request.env.user.has_group('unifi_integration.group_udm_pro_manager'):
            return request.render('unifi_integration.access_denied', {
                'error_message': _("You don't have permission to restart devices.")
            })
            
        # Get saved UDM Pro configurations for the form
        configs = request.env['udm.configuration'].sudo().search([])
        return request.render('unifi_integration.restart_device_form', {
            'configs': configs
        })
        
    @http.route('/udm_pro/restart_device', type='http', auth='user', website=True, methods=['POST'])
    def restart_device(self, **post):
        """Process the request to restart a UDM Pro device"""
        if not request.env.user.has_group('unifi_integration.group_udm_pro_manager'):
            return request.render('unifi_integration.access_denied', {
                'error_message': _("You don't have permission to restart devices.")
            })
        
        config_id_str = post.get('config_id')
        if not config_id_str:
            raise ValueError(_('Configuration ID is required'))
        config_id = int(config_id_str)
        mac_address = post.get('mac_address')
        
        if not mac_address:
            return request.render('unifi_integration.restart_device_form', {
                'error_message': _("Please provide the MAC address of the device to restart."),
                'configs': request.env['udm.configuration'].sudo().search([])
            })
        
        try:
            # Get the configuration
            config = request.env['udm.configuration'].sudo().browse(config_id)
            if not config.exists():
                raise ValueError(_("Configuration not found"))
                
            # Initialiser le client UDM Pro
            client = UdmProClient(
                host=config.host,
                username=config.username,
                password=config.password,
                port=config.port or 443
            )
            
            # Authenticate the client
            if not client.login():
                return request.render('unifi_integration.restart_device_form', {
                    'error_message': _("Authentication failed. Please check the configuration credentials."),
                    'configs': request.env['udm.configuration'].sudo().search([])
                })
            
            # Restart the device
            success = client.restart_device(mac_address)
            if not success:
                return request.render('unifi_integration.restart_device_form', {
                    'error_message': _("Failed to restart the device. Please check logs for details."),
                    'configs': request.env['udm.configuration'].sudo().search([])
                })
                
            return request.render('unifi_integration.restart_success', {
                'mac_address': mac_address
            })
            
        except (ConnectionError, RequestException) as e:
            _logger.error("Error during UDM Pro device restart: %s", str(e))
            return request.render('unifi_integration.restart_device_form', {
                'error_message': _("Error connecting to UDM Pro: %s") % str(e),
                'configs': request.env['udm.configuration'].sudo().search([])
            })
        except Exception as e:  # pylint: disable=broad-except
            _logger.exception("Unexpected error during UDM Pro device restart")
            return request.render('unifi_integration.restart_device_form', {
                'error_message': _("An unexpected error occurred: %s") % str(e),
                'configs': request.env['udm.configuration'].sudo().search([])
            })
    
    @http.route('/udm_pro/generate_hosts', type='http', auth='user', website=True)
    def generate_hosts_form(self):
        """Display the form to generate a hosts file from UDM Pro"""
        # Get saved UDM Pro configurations for the form
        configs = request.env['udm.configuration'].sudo().search([])
        return request.render('unifi_integration.generate_hosts_form', {
            'configs': configs,
            'fixed_only': True,
            'lowercase_hostnames': True
        })
        
    @http.route('/udm_pro/generate_hosts', type='http', auth='user', website=True, methods=['POST'])
    def generate_hosts(self, **post):
        """Generate a hosts file from UDM Pro network clients"""
        config_id_str = post.get('config_id')
        if not config_id_str:
            raise ValueError(_('Configuration ID is required'))
        config_id = int(config_id_str)
        fixed_only = post.get('fixed_only') == 'on'
        lowercase_hostnames = post.get('lowercase_hostnames') == 'on'
        
        try:
            # Get the configuration
            config = request.env['udm.configuration'].sudo().browse(config_id)
            if not config.exists():
                raise ValueError(_("Configuration not found"))
                
            # Initialize the UDM Pro client with advanced options
            client = UdmProClient(
                host=config.host,
                username=config.username,
                password=config.password,
                port=config.port or 443,
                fixed_only=fixed_only,
                lowercase_hostnames=lowercase_hostnames
            )
            
            # Authenticate the client
            if not client.login():
                return request.render('unifi_integration.generate_hosts_form', {
                    'error_message': _("Authentication failed. Please check the configuration credentials."),
                    'configs': request.env['udm.configuration'].sudo().search([]),
                    'fixed_only': fixed_only,
                    'lowercase_hostnames': lowercase_hostnames
                })
            
            # Generate the hosts file
            hosts_content = client.generate_hosts_file()
            
            # Return the content as a downloadable file
            # Create and configure the HTTP response
            try:
                response = request.make_response(hosts_content)
                if not response:
                    raise ValueError(_('Failed to create response'))
                response.headers['Content-Type'] = 'text/plain'
                response.headers['Content-Disposition'] = 'attachment; filename=udm_hosts.txt'
                return response
            except (AttributeError, TypeError) as e:
                _logger.error('Error creating response: %s', str(e))
                raise ValueError(_('Failed to create response'))
            
        except (ConnectionError, RequestException) as e:
            _logger.error("Error during UDM Pro hosts file generation: %s", str(e))
            return request.render('unifi_integration.generate_hosts_form', {
                'error_message': _("Error connecting to UDM Pro: %s") % str(e),
                'configs': request.env['udm.configuration'].sudo().search([]),
                'fixed_only': fixed_only,
                'lowercase_hostnames': lowercase_hostnames
            })
        except Exception as e:  # pylint: disable=broad-except
            _logger.exception("Unexpected error during UDM Pro hosts file generation")
            return request.render('unifi_integration.generate_hosts_form', {
                'error_message': _("An unexpected error occurred: %s") % str(e),
                'configs': request.env['udm.configuration'].sudo().search([]),
                'fixed_only': fixed_only,
                'lowercase_hostnames': lowercase_hostnames
            })
    
    @http.route('/udm_pro/network_clients', type='http', auth='user', website=True)
    def network_clients_form(self):
        """Display the form to view UDM Pro network clients"""
        # Get saved UDM Pro configurations for the form
        configs = request.env['udm.configuration'].sudo().search([])
        return request.render('unifi_integration.network_clients_form', {
            'configs': configs,
            'fixed_only': False,
            'lowercase_hostnames': True
        })
        
    @http.route('/udm_pro/network_clients', type='http', auth='user', website=True, methods=['POST'])
    def get_network_clients(self, **post):
        """Get and display the list of UDM Pro network clients"""
        config_id_str = post.get('config_id')
        if not config_id_str:
            raise ValueError(_('Configuration ID is required'))
        config_id = int(config_id_str)
        fixed_only = post.get('fixed_only') == 'on'
        lowercase_hostnames = post.get('lowercase_hostnames') == 'on'
        
        try:
            # Get the configuration
            config = request.env['udm.configuration'].sudo().browse(config_id)
            if not config.exists():
                raise ValueError(_("Configuration not found"))
                
            # Initialize the UDM Pro client with advanced options
            client = UdmProClient(
                host=config.host,
                username=config.username,
                password=config.password,
                port=config.port or 443,
                fixed_only=fixed_only,
                lowercase_hostnames=lowercase_hostnames
            )
            
            # Authenticate the client
            if not client.login():
                return request.render('unifi_integration.network_clients_form', {
                    'error_message': _("Authentication failed. Please check the configuration credentials."),
                    'configs': request.env['udm.configuration'].sudo().search([]),
                    'fixed_only': fixed_only,
                    'lowercase_hostnames': lowercase_hostnames
                })
            
            # Get network clients
            network_clients = client.get_network_clients()
            
            return request.render('unifi_integration.network_clients_result', {
                'clients': network_clients,
                'config': config
            })
            
        except (ConnectionError, RequestException) as e:
            _logger.error("Error retrieving UDM Pro network clients: %s", str(e))
            return request.render('unifi_integration.network_clients_form', {
                'error_message': _("Error connecting to UDM Pro: %s") % str(e),
                'configs': request.env['udm.configuration'].sudo().search([]),
                'fixed_only': fixed_only,
                'lowercase_hostnames': lowercase_hostnames
            })
        except ValueError as e:
            _logger.error("Value error retrieving UDM Pro network clients: %s", str(e))
            return request.render('unifi_integration.network_clients_form', {
                'error_message': _("Configuration error: %s") % str(e),
                'configs': request.env['udm.configuration'].sudo().search([]),
                'fixed_only': fixed_only,
                'lowercase_hostnames': lowercase_hostnames
            })
        except (AttributeError, KeyError) as e:
            _logger.error("Data format error retrieving UDM Pro network clients: %s", str(e))
            return request.render('unifi_integration.network_clients_form', {
                'error_message': _("Data error: %s") % str(e),
                'configs': request.env['udm.configuration'].sudo().search([]),
                'fixed_only': fixed_only,
                'lowercase_hostnames': lowercase_hostnames
            })
        except Exception as e:  # pylint: disable=broad-except
            # Keep this generic exception as a last resort, with an explicit warning for pylint
            _logger.exception("Unexpected error retrieving UDM Pro network clients")
            return request.render('unifi_integration.network_clients_form', {
                'error_message': _("An unexpected error occurred: %s") % str(e),
                'configs': request.env['udm.configuration'].sudo().search([]),
                'fixed_only': fixed_only,
                'lowercase_hostnames': lowercase_hostnames
            })
    
    @http.route('/udm_pro/import_config', type='http', auth='user', website=True)
    def import_config_form(self):
        """Display the UDM Pro configuration import form"""
        return request.render('unifi_integration.import_config_form', {})
    
    @http.route('/udm_pro/import_config', type='http', auth='user', website=True, methods=['POST'])
    def import_config(self, **post):
        """Import UDM Pro configuration from the device"""
        if not request.env.user.has_group('unifi_integration.group_udm_pro_manager'):
            return request.render('unifi_integration.access_denied', {
                'error_message': _("You don't have permission to import configurations.")
            })
        
        host = post.get('host')
        username = post.get('username')
        password = post.get('password')
        port_str = post.get('port')
        port = int(port_str) if port_str else 443
        
        if not all([host, username, password]):
            return request.render('unifi_integration.import_config_form', {
                'error_message': _("Please provide all required fields."),
                'host': host,
                'username': username,
                'port': port
            })
        
        try:
            # Use the API client to get the configuration
            client = UdmProClient(host, username, password, port)
            if not client.login():
                return request.render('unifi_integration.import_config_form', {
                    'error_message': _("Authentication failed. Please check your credentials."),
                    'host': host,
                    'username': username,
                    'port': port
                })
            
            config_data = client.get_full_configuration()
            
            # Import the configuration into Odoo
            config_id = request.env['udm.configuration'].sudo().import_configuration(config_data)
            
            return request.redirect('/web#id=%s&model=udm.configuration&view_type=form' % config_id)
            
        except (ConnectionError, RequestException) as e:
            _logger.error("Error during UDM Pro configuration import: %s", str(e))
            return request.render('unifi_integration.import_config_form', {
                'error_message': _("Error connecting to UDM Pro: %s") % str(e),
                'host': host,
                'username': username,
                'port': port
            })
        except (ValueError, TypeError, AttributeError) as e:
            _logger.error("Data processing error during UDM Pro configuration import: %s", str(e))
            return request.render('unifi_integration.import_config_form', {
                'error_message': _("Error processing data: %s") % str(e),
                'host': host,
                'username': username,
                'port': port
            })
        except Exception as e:  # pylint: disable=broad-except
            _logger.exception("Unexpected error during UDM Pro configuration import")
            return request.render('unifi_integration.import_config_form', {
                'error_message': _("An unexpected error occurred. Please check server logs."),
                'host': host,
                'username': username,
                'port': port
            })


class UdmProClient:
    """Client to interact with the UDM Pro API."""
    
    # API endpoints
    API_LOGIN_ENDPOINT = '/api/auth/login'
    API_SYSTEM_INFO_ENDPOINT = '/api/system'
    API_NETWORK_ENDPOINT = '/api/networks'
    API_DEVICES_ENDPOINT = '/api/devices'
    API_USERS_ENDPOINT = '/api/users'
    API_SETTINGS_ENDPOINT = '/api/settings'
    API_FIREWALL_ENDPOINT = '/api/firewall'
    
    # New endpoints inspired by the Go client
    API_ACTIVE_CLIENTS_ENDPOINT = '/proxy/network/api/s/{site}/stat/sta'
    API_CONFIGURED_CLIENTS_ENDPOINT = '/proxy/network/api/s/{site}/list/user'
    API_DEVICE_RESTART_ENDPOINT = '/proxy/network/api/s/{site}/cmd/devmgr'
    
    def __init__(self, host, username, password, port=443, verify_ssl=False, site='default', fixed_only=True, lowercase_hostnames=True, debug=False):
        """
        Initialize the UDM Pro API client.
        
        Args:
            host (str): IP address or hostname of the UDM Pro
            username (str): Username for the API
            password (str): Password for the API
            port (int): Port for connection (default 443)
            verify_ssl (bool): Verify SSL certificate (default False)
            site (str): Site identifier for UniFi API (default 'default')
            fixed_only (bool): Only consider clients with fixed IP address (default True)
            lowercase_hostnames (bool): Convert hostnames to lowercase (default True)
            debug (bool): Enable debug mode for HTTP requests (default False)
        """
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.verify_ssl = verify_ssl
        self.site = site
        self.fixed_only = fixed_only
        self.lowercase_hostnames = lowercase_hostnames
        self.debug = debug
        self.base_url = f"https://{host}:{port}"
        self.token = None
        self.csrf_token = None
        self.session = requests.Session()
        self.session.verify = verify_ssl
        
    def _get_auth_headers(self):
        """Return authentication headers."""
        if not self.token:
            raise ValueError("Not authenticated. Call login() first.")
            
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # Add CSRF token if available
        if self.csrf_token:
            headers["X-Csrf-Token"] = self.csrf_token
            
        return headers
    
    def login(self):
        """
        Authenticates the client with the UDM Pro API.
        
        Returns:
            bool: True if authentication succeeded, False otherwise
        """
        try:
            login_url = f"{self.base_url}{self.API_LOGIN_ENDPOINT}"
            payload = {
                "username": self.username,
                "password": self.password
            }
            
            _logger.debug("Attempting to connect to %s", login_url)
            response = self.session.post(login_url, json=payload)
            response.raise_for_status()
            
            # Capture CSRF token if it exists
            csrf_token = response.headers.get('X-Csrf-Token')
            if csrf_token:
                self.csrf_token = csrf_token
                _logger.debug("CSRF token captured: %s", csrf_token)
            
            data = response.json()
            if not data.get('token'):
                _logger.error("No token was returned by the API")
                return False
                
            self.token = data['token']
            _logger.debug("Authentication successful")
            return True
            
        except RequestException as e:
            _logger.error("Authentication error: %s", str(e))
            return False
    
    def _make_api_request(self, method, endpoint, params=None, data=None, retry=True):
        """
        Makes an API request.
        
        Args:
            method (str): HTTP method (GET, POST, etc.)
            endpoint (str): API endpoint
            params (dict): Request parameters
            data (dict): Data to send in request body
            retry (bool): Retry on authentication error
            
        Returns:
            dict: JSON response from API
        """
        if not self.token and retry:
            _logger.debug("Not authenticated, attempting authentication")
            if not self.login():
                raise ConnectionError("Unable to authenticate with UDM Pro API")
        
        url = f"{self.base_url}{endpoint}"
        try:
            _logger.debug("Request %s to %s", method, url)
            headers = self._get_auth_headers()
            response = None
            
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=data
                )
                
                # Capture CSRF token if it exists in the response
                csrf_token = response.headers.get('X-Csrf-Token')
                if csrf_token and csrf_token != self.csrf_token:
                    self.csrf_token = csrf_token
                    _logger.debug("CSRF token updated: %s", csrf_token)
                
                response.raise_for_status()
                return response.json()
                
            except RequestException as request_error:
                if response and (response.status_code == 401 or response.status_code == 403):
                    if retry:
                        _logger.debug("Token expired, attempting re-authentication")
                        self.token = None
                        return self._make_api_request(method, endpoint, params, data, retry=False)
                _logger.error("API error (%s %s): %s", method, url, str(request_error))
                raise
                
        except Exception as e:
            _logger.error("Unexpected error in API request: %s", str(e))
            raise
    
    def get_system_info(self):
        """
        Gets system information from UDM Pro.
        
        Returns:
            dict: System information
        """
        return self._make_api_request('GET', self.API_SYSTEM_INFO_ENDPOINT)
    
    def get_networks(self):
        """
        Gets network configuration.
        
        Returns:
            dict: Network configuration
        """
        return self._make_api_request('GET', self.API_NETWORK_ENDPOINT)
    
    def get_devices(self):
        """
        Gets the list of devices.
        
        Returns:
            dict: List of devices
        """
        return self._make_api_request('GET', self.API_DEVICES_ENDPOINT)
    
    def get_users(self):
        """
        Gets the list of users.
        
        Returns:
            dict: List of users
        """
        return self._make_api_request('GET', self.API_USERS_ENDPOINT)
    
    def get_settings(self):
        """
        Gets general settings.
        
        Returns:
            dict: General settings
        """
        return self._make_api_request('GET', self.API_SETTINGS_ENDPOINT)
    
    def get_firewall_rules(self):
        """
        Gets firewall rules.
        
        Returns:
            dict: Firewall rules
        """
        return self._make_api_request('GET', self.API_FIREWALL_ENDPOINT)
    
    def get_active_clients(self):
        """
        Gets the list of currently connected clients.
        
        Returns:
            list: List of active clients
        """
        endpoint = self.API_ACTIVE_CLIENTS_ENDPOINT.format(site=self.site)
        response = self._make_api_request('GET', endpoint)
        
        if not response or 'data' not in response:
            return []
            
        return response.get('data', [])
        
    def get_configured_clients(self):
        """
        Gets the list of statically configured clients.
        
        Returns:
            list: List of configured clients
        """
        endpoint = self.API_CONFIGURED_CLIENTS_ENDPOINT.format(site=self.site)
        response = self._make_api_request('GET', endpoint)
        
        if not response or 'data' not in response:
            return []
            
        return response.get('data', [])
        
    def restart_device(self, mac_address):
        """
        Restarts a device managed by UDM Pro (e.g. WiFi access point).
        Requires 'site admin' level permissions.
        
        Args:
            mac_address (str): MAC address of device to restart
            
        Returns:
            bool: True if operation succeeded, False otherwise
        """
        endpoint = self.API_DEVICE_RESTART_ENDPOINT.format(site=self.site)
        payload = {
            'mac': mac_address,
            'reboot_type': 'soft',
            'cmd': 'restart'
        }
        
        try:
            response = self._make_api_request('POST', endpoint, data=payload)
            if response and response.get('meta', {}).get('rc') == 'ok':
                return True
            return False
        except Exception as e:  # pylint: disable=broad-except
            _logger.error("Error while restarting device %s: %s", mac_address, str(e))
            return False
            
    def get_network_clients(self):
        """
        Gets all network clients (active and/or configured according to parameters).
        
        Returns:
            list: List of network clients
        """
        clients = []
        
        # Always include statically configured clients
        configured_clients = self.get_configured_clients()
        clients.extend(configured_clients)
        
        # Include active clients if fixed_only is False
        if not self.fixed_only:
            active_clients = self.get_active_clients()
            clients.extend(active_clients)
            
        # Process hostnames if needed
        if self.lowercase_hostnames:
            for client in clients:
                if client.get('hostname'):
                    client['hostname'] = client['hostname'].lower()
                if client.get('name'):
                    client['name'] = client['name'].lower()
                    
        return clients
    
    def generate_hosts_file(self):
        """
        Generates a hosts file from network clients.
        
        Returns:
            str: Content of hosts file
        """
        clients = self.get_network_clients()
        hosts_content = "# UDM Pro Generated Hosts File\n"
        hosts_content += "# Generated on {}\n\n".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        for client in clients:
            name = client.get('name') or client.get('hostname')
            ip = client.get('fixed_ip') or client.get('ip')
            mac = client.get('mac', '')
            
            if name and ip:
                hosts_content += "{:16s} {:30s} # {}\n".format(ip, name, mac)
                
        return hosts_content
    
    def get_full_configuration(self):
        """
        Gets complete UDM Pro configuration.
        
        Returns:
            dict: Complete UDM Pro configuration
        """
        # Authenticate first
        if not self.token and not self.login():
            raise ConnectionError("Authentication failed while retrieving complete configuration")
        
        try:
            # Get each part of the configuration
            system_info = self.get_system_info()
            networks = self.get_networks()
            devices = self.get_devices()
            users = self.get_users()
            settings = self.get_settings()
            firewall = self.get_firewall_rules()
            
            # Also get network clients (new feature)
            network_clients = self.get_network_clients()
            
            # Combine all parts into a single dictionary
            return {
                'system_info': system_info,
                'networks': networks,
                'devices': devices,
                'users': users,
                'settings': settings,
                'firewall': firewall,
                'network_clients': network_clients
            }
            
        except RequestException as e:
            _logger.error("Error while retrieving complete configuration: %s", str(e))
            raise
