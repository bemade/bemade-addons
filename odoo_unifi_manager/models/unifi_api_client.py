import json
import logging
import requests
import urllib3
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

class UnifiApiClient:
    """Custom UniFi API Client implementation."""
    
    def __init__(self, host: str, username: str, password: str, port: int = 8443, 
                 is_udm: bool = False, verify_ssl: bool = False, timeout: int = 10):
        """Initialize the UniFi API client.
        
        Args:
            host: Hostname or IP address of the UniFi Controller
            username: Username for API authentication
            password: Password for API authentication
            port: Port number for the API (default: 8443)
            is_udm: Whether this is a UDM Pro device
            verify_ssl: Whether to verify SSL certificates
            timeout: Request timeout in seconds
        """
        if not host or not username or not password:
            raise ValidationError("Host, username and password are required")
        
        self.host = host
        self.port = port
        self.is_udm = is_udm
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.site_id = 'default'
        
        # Disable SSL warnings if verify_ssl is False
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Setup session
        self.session = requests.Session()
        self.session.verify = verify_ssl
        
        # Base URLs
        if is_udm:
            self.base_url = f"https://{host}"
            self.api_url = f"https://{host}/proxy/network"
            self.auth_url = f"https://{host}/api/auth/login"
        else:
            self.base_url = f"https://{host}:{port}"
            self.api_url = self.base_url
            self.auth_url = f"{self.base_url}/api/login"
        
        _logger.info(f"Initialized with base_url={self.base_url}, api_url={self.api_url}")
        
        try:
            self._login(username, password)
            _logger.info("Successfully authenticated with UniFi controller")
            
            # Only try to discover sites for non-UDM controllers
            if not is_udm:
                try:
                    sites = self.get_sites()
                    _logger.info(f"Available sites: {sites}")
                    if sites:
                        # If 'default' site doesn't exist, use the first available site
                        site_exists = any(site.get('name') == 'default' for site in sites)
                        if not site_exists and sites:
                            self.site_id = sites[0].get('name')
                            _logger.info(f"Using site: {self.site_id}")
                except Exception as e:
                    _logger.warning(f"Failed to get sites, using default site: {str(e)}")
            
        except Exception as e:
            _logger.error(f"Failed to initialize UniFi controller: {str(e)}")
            raise ValidationError(f"Failed to initialize UniFi controller: {str(e)}")
    
    def _login(self, username: str, password: str):
        """Authenticate with the UniFi Controller."""
        _logger.info(f"Attempting login to {self.auth_url}")
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Add CSRF token for UDM Pro if available
        if self.is_udm and hasattr(self, 'csrf_token'):
            headers['X-CSRF-Token'] = self.csrf_token
        
        data = {
            'username': username,
            'password': password,
            'remember': True
        }
        
        try:
            _logger.info(f"Making login request to {self.auth_url}")
            response = self.session.post(
                self.auth_url,
                headers=headers,
                json=data,
                timeout=self.timeout
            )
            
            _logger.info(f"Login response status: {response.status_code}")
            _logger.info(f"Login response headers: {response.headers}")
            _logger.info(f"Login response content: {response.text}")
            
            if not response.ok:
                _logger.error(f"Login failed with status {response.status_code}")
                _logger.error(f"Response content: {response.text}")
            
            response.raise_for_status()
            
            # Store cookies and CSRF token for subsequent requests
            self.session.cookies.update(response.cookies)
            if self.is_udm:
                self.csrf_token = response.headers.get('X-CSRF-Token')
                _logger.info(f"Stored CSRF token: {self.csrf_token}")
            _logger.info("Successfully logged in and stored session cookies")
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"Login request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                _logger.error(f"Error response content: {e.response.text}")
            raise ValidationError(f"Login failed: {str(e)}")
    
    def _api_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make an API request to the UniFi Controller."""
        if self.is_udm:
            # For UDM Pro, check if endpoint already has proxy/network prefix
            if endpoint.startswith('proxy/network/'):
                url = f"{self.base_url}/{endpoint}"
            else:
                # If no prefix, use api_url which includes the proxy/network prefix
                url = f"{self.api_url}/{endpoint.lstrip('/')}"
        else:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        _logger.info(f"Making {method} request to {url}")
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        if self.is_udm and hasattr(self, 'csrf_token'):
            headers['X-CSRF-Token'] = self.csrf_token
            
        try:
            if data and method in ['POST', 'PUT', 'PATCH']:
                response = self.session.request(
                    method,
                    url,
                    headers=headers,
                    json=data,  # Use json parameter for requests that send data
                    timeout=self.timeout
                )
            else:
                response = self.session.request(
                    method,
                    url,
                    headers=headers,
                    timeout=self.timeout
                )
            
            _logger.info(f"Response status: {response.status_code}")
            _logger.info(f"Response headers: {response.headers}")
            _logger.info(f"Response content: {response.text}")
            
            response.raise_for_status()
            
            if response.text:
                return response.json()
            return None
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"API request failed with status {e.response.status_code if hasattr(e, 'response') and e.response else 'unknown'}")
            if hasattr(e, 'response') and e.response is not None:
                _logger.error(f"Error response content: {e.response.text}")
            raise
    
    def get_sites(self) -> list:
        """Get list of available sites."""
        try:
            if self.is_udm:
                return [{'name': 'default'}]
            
            response = self._api_request('GET', 'api/self/sites')
            return response.get('data', [])
        except Exception as e:
            _logger.error(f"Failed to get sites: {str(e)}")
            return []
    
    def get_firewall_rules(self, site_id=None):
        """Get all firewall rules for a site."""
        site = site_id or self.site_id
        if self.is_udm:
            # For UDM Pro, use the network proxy endpoint
            return self._api_request('GET', f'proxy/network/api/s/{site}/firewallrule')
        return self._api_request('GET', f'api/s/{site}/rest/firewallrule')

    def get_active_firewall_rules(self, site_id=None):
        """Get active firewall rules for a site."""
        site = site_id or self.site_id
        return self._api_request('GET', f'api/s/{site}/stat/firewallrule')

    def get_firewall_groups(self, site_id=None):
        """Get firewall groups for a site."""
        site = site_id or self.site_id
        return self._api_request('GET', f'api/s/{site}/rest/firewallgroup')

    def update_firewall_rule(self, rule_id: str, data: dict, site_id=None):
        """Update a firewall rule."""
        site = site_id or self.site_id
        return self._api_request('PUT', f'api/s/{site}/rest/firewallrule/{rule_id}', data)

    def toggle_firewall_rule(self, rule_id: str, enabled: bool, site_id=None):
        """Enable or disable a firewall rule."""
        return self.update_firewall_rule(rule_id, {'enabled': enabled}, site_id)

    def get_firewall_rules(self) -> list:
        """Get firewall rules from the controller."""
        try:
            if self.is_udm:
                # Try UDM Pro Network Settings endpoint first
                try:
                    _logger.info("Trying network settings endpoint")
                    response = self._api_request('GET', 'proxy/network/api/s/default/rest/setting/firewall')
                    _logger.info(f"Network settings response: {response}")
                    if response and isinstance(response, dict):
                        firewall_settings = response.get('data', [{}])[0]
                        if firewall_settings:
                            _logger.info(f"Found firewall settings: {firewall_settings}")
                            rules = []
                            # Get WAN rules
                            wan_in = firewall_settings.get('wan_in', [])
                            for rule in wan_in:
                                rule['ruleset'] = 'WAN_IN'
                                rules.append(rule)
                            wan_out = firewall_settings.get('wan_out', [])
                            for rule in wan_out:
                                rule['ruleset'] = 'WAN_OUT'
                                rules.append(rule)
                            wan_local = firewall_settings.get('wan_local', [])
                            for rule in wan_local:
                                rule['ruleset'] = 'WAN_LOCAL'
                                rules.append(rule)
                            # Get LAN rules
                            lan_in = firewall_settings.get('lan_in', [])
                            for rule in lan_in:
                                rule['ruleset'] = 'LAN_IN'
                                rules.append(rule)
                            lan_out = firewall_settings.get('lan_out', [])
                            for rule in lan_out:
                                rule['ruleset'] = 'LAN_OUT'
                                rules.append(rule)
                            lan_local = firewall_settings.get('lan_local', [])
                            for rule in lan_local:
                                rule['ruleset'] = 'LAN_LOCAL'
                                rules.append(rule)
                            _logger.info(f"Found {len(rules)} firewall rules")
                            return rules
                except Exception as e:
                    _logger.warning(f"Failed to get rules from network settings: {str(e)}")

            # Try site-specific endpoint for non-UDM or as fallback
            endpoint = f'api/s/{self.site_id}/rest/setting/firewall'
            _logger.info(f"Trying {endpoint} endpoint")
            response = self._api_request('GET', endpoint)
            _logger.info(f"Response from {endpoint}: {response}")
            if response and isinstance(response, dict):
                firewall_settings = response.get('data', [{}])[0]
                if firewall_settings:
                    rules = []
                    # Get WAN rules
                    wan_in = firewall_settings.get('wan_in', [])
                    for rule in wan_in:
                        rule['ruleset'] = 'WAN_IN'
                        rules.append(rule)
                    wan_out = firewall_settings.get('wan_out', [])
                    for rule in wan_out:
                        rule['ruleset'] = 'WAN_OUT'
                        rules.append(rule)
                    wan_local = firewall_settings.get('wan_local', [])
                    for rule in wan_local:
                        rule['ruleset'] = 'WAN_LOCAL'
                        rules.append(rule)
                    # Get LAN rules
                    lan_in = firewall_settings.get('lan_in', [])
                    for rule in lan_in:
                        rule['ruleset'] = 'LAN_IN'
                        rules.append(rule)
                    lan_out = firewall_settings.get('lan_out', [])
                    for rule in lan_out:
                        rule['ruleset'] = 'LAN_OUT'
                        rules.append(rule)
                    lan_local = firewall_settings.get('lan_local', [])
                    for rule in lan_local:
                        rule['ruleset'] = 'LAN_LOCAL'
                        rules.append(rule)
                    _logger.info(f"Found {len(rules)} firewall rules")
                    return rules
            
            _logger.warning("Could not retrieve firewall rules from any known endpoint")
            return []
            
        except Exception as e:
            _logger.error(f"Failed to retrieve firewall rules: {str(e)}")
            raise UserError(f"Failed to retrieve firewall rules: {str(e)}")
    
    def create_firewall_group(self, data: dict, site_id=None) -> dict:
        """Create a firewall group.
        
        Args:
            data: Dictionary containing the firewall group data
            site_id: Optional site ID. If not provided, uses the default site
            
        Returns:
            dict: Created firewall group data
        """
        try:
            _logger.info(f"Creating firewall group: {data}")
            site = site_id or self.site_id
            
            if self.is_udm:
                endpoint = f'proxy/network/api/s/{site}/rest/firewallgroup'
            else:
                endpoint = f'api/s/{site}/rest/firewallgroup'
            
            return self._api_request('POST', endpoint, data=data)
            
        except Exception as e:
            _logger.error(f"Failed to create firewall group: {str(e)}")
            raise UserError(f"Failed to create firewall group: {str(e)}")
    
    def ensure_default_firewall_groups(self, site_id=None):
        """Ensure default firewall groups exist.
        
        Creates default LAN and WAN groups if they don't exist.
        """
        try:
            _logger.info("Checking for default firewall groups")
            groups = self.get_firewall_groups(site_id)
            
            if not groups:
                _logger.info("No firewall groups found, creating defaults")
                defaults = [
                    {
                        'name': 'Default LAN',
                        'group_type': 'address-group',
                        'group_members': ['192.168.0.0/16', '172.16.0.0/12', '10.0.0.0/8'],
                        'group_description': 'Default LAN networks'
                    },
                    {
                        'name': 'Default WAN',
                        'group_type': 'address-group',
                        'group_members': ['0.0.0.0/0'],
                        'group_description': 'Default WAN networks'
                    }
                ]
                
                for group in defaults:
                    try:
                        _logger.info(f"Creating firewall group: {group}")
                        self.create_firewall_group(group, site_id)
                    except Exception as e:
                        _logger.warning(f"Failed to create firewall group: {str(e)}")
                
        except Exception as e:
            _logger.error(f"Failed to ensure default firewall groups: {str(e)}")
    
    def list_devices(self) -> list:
        """Get a list of all devices from the UniFi Controller.
        
        Returns:
            list: List of device dictionaries containing device information
        """
        try:
            _logger.info("Attempting to get all devices")
            devices = []
            
            # Try primary endpoint first
            try:
                if self.is_udm:
                    endpoint = 'proxy/network/api/s/default/stat/device'  # UDM Pro endpoint
                else:
                    endpoint = f'api/s/{self.site_id}/stat/device'
                    
                _logger.info(f"Getting devices from endpoint: {endpoint}")
                response = self._api_request('GET', endpoint)
                
                if isinstance(response, dict):
                    devices = response.get('data', [])
                else:
                    devices = response
                    
                _logger.info(f"Found {len(devices)} devices")
                
            except Exception as e:
                _logger.warning(f"Failed to get devices using primary endpoint: {str(e)}")
                
                # Try fallback endpoint for UDM Pro
                try:
                    if self.is_udm:
                        endpoint = 'proxy/network/v2/api/site/default/devices'  # New UDM Pro endpoint
                    else:
                        endpoint = f'api/s/{self.site_id}/stat/device/basic'
                        
                    _logger.info(f"Getting devices from endpoint: {endpoint}")
                    response = self._api_request('GET', endpoint)
                    
                    if isinstance(response, dict):
                        devices = response.get('data', [])
                    else:
                        devices = response
                        
                    _logger.info(f"Found {len(devices)} devices using fallback endpoint")
                    
                except Exception as e:
                    _logger.warning(f"Failed to get devices using fallback endpoint: {str(e)}")
            
            _logger.info(f"Total devices retrieved: {len(devices)}")
            if devices:
                _logger.info("Sample device data:")
                _logger.info(str(devices[0]))
            return devices
            
        except Exception as e:
            _logger.error(f"Failed to get devices: {str(e)}")
            raise UserError(f"Failed to get devices: {str(e)}")
    
    def list_clients(self) -> list:
        """Get a list of all clients from the UniFi Controller.
        
        Returns:
            list: List of client dictionaries containing client information
        """
        try:
            _logger.info("Attempting to get all clients")
            clients = []
            
            # Try to get all clients at once
            try:
                if self.is_udm:
                    endpoint = 'proxy/network/api/s/default/stat/sta'
                else:
                    endpoint = f'api/s/{self.site_id}/stat/sta'
                
                _logger.info(f"Attempting to get all clients using endpoint: {endpoint}")
                response = self._api_request('GET', endpoint)
                
                if isinstance(response, dict):
                    clients = response.get('data', [])
                else:
                    clients = response
                
                _logger.info(f"Retrieved {len(clients)} clients")
                
            except Exception as e:
                _logger.warning(f"Failed to get clients using primary endpoint: {str(e)}")
                
                # Fallback to alternative endpoint
                try:
                    if self.is_udm:
                        endpoint = 'proxy/network/v2/api/site/default/clients'
                    else:
                        endpoint = f'api/s/{self.site_id}/stat/alluser'
                    
                    _logger.info(f"Trying to get clients from endpoint: {endpoint}")
                    response = self._api_request('GET', endpoint)
                    
                    if isinstance(response, dict):
                        clients = response.get('data', [])
                    else:
                        clients = response
                    
                    _logger.info(f"Found {len(clients)} clients using fallback endpoint")
                    
                except Exception as e:
                    _logger.warning(f"Failed to get clients using fallback endpoint: {str(e)}")
            
            _logger.info(f"Total clients retrieved: {len(clients)}")
            if clients:
                _logger.info("Sample client data:")
                _logger.info(str(clients[0]))
            return clients
            
        except Exception as e:
            _logger.error(f"Failed to get clients: {str(e)}")
            raise UserError(f"Failed to get clients: {str(e)}")
    
    def list_networks(self) -> list:
        """Get a list of all networks from the UniFi Controller.
        
        Returns:
            list: List of network dictionaries containing network information
        """
        try:
            _logger.info("Attempting to get all networks")
            
            if self.is_udm:
                endpoint = 'proxy/network/api/s/default/rest/networkconf'
            else:
                endpoint = f'api/s/{self.site_id}/rest/networkconf'
            
            _logger.info(f"Attempting to get networks using endpoint: {endpoint}")
            response = self._api_request('GET', endpoint)
            
            if isinstance(response, dict):
                networks = response.get('data', [])
            else:
                networks = response
            
            _logger.info(f"Retrieved {len(networks)} networks")
            if networks:
                _logger.info("Sample network data:")
                _logger.info(str(networks[0]))
            return networks
            
        except Exception as e:
            _logger.error(f"Failed to get networks: {str(e)}")
            raise UserError(f"Failed to get networks: {str(e)}")

    def list_sites(self) -> list:
        """Get a list of all sites from the UniFi Controller.
        
        Returns:
            list: List of site dictionaries containing site information
        """
        try:
            _logger.info("Attempting to get all sites")
            
            if self.is_udm:
                # UDM Pro typically has only one site
                return [{
                    'name': 'default',
                    'desc': 'Default',
                    '_id': 'default',
                    'role': 'admin'
                }]
            
            endpoint = 'api/self/sites'
            _logger.info(f"Attempting to get sites using endpoint: {endpoint}")
            response = self._api_request('GET', endpoint)
            
            if isinstance(response, dict):
                sites = response.get('data', [])
            else:
                sites = response
            
            _logger.info(f"Retrieved {len(sites)} sites")
            if sites:
                _logger.info("Sample site data:")
                _logger.info(str(sites[0]))
            return sites
            
        except Exception as e:
            _logger.error(f"Failed to get sites: {str(e)}")
            raise UserError(f"Failed to get sites: {str(e)}")
    
    def get_wifis(self, site_id=None) -> list:
        """Get a list of all WiFi networks from the UniFi Controller.
        
        Args:
            site_id: Optional site ID. If not provided, uses the default site.
            
        Returns:
            list: List of WiFi network configurations
        """
        try:
            _logger.info("Attempting to get WiFi networks")
            site = site_id or self.site_id
            
            # Try primary endpoint first
            try:
                if self.is_udm:
                    endpoint = f'proxy/network/api/s/{site}/rest/wlanconf'
                else:
                    endpoint = f'api/s/{site}/rest/wlanconf'
                
                _logger.info(f"Getting WiFi networks from endpoint: {endpoint}")
                response = self._api_request('GET', endpoint)
                
                if isinstance(response, dict):
                    networks = response.get('data', [])
                else:
                    networks = response or []
                
                _logger.info(f"Found {len(networks)} WiFi networks")
                if networks:
                    _logger.info("Sample WiFi network data:")
                    _logger.info(str(networks[0]))
                return networks
                
            except Exception as e:
                _logger.error(f"Failed to get WiFi networks: {str(e)}")
                raise
                
        except Exception as e:
            _logger.error(f"Failed to get WiFi networks: {str(e)}")
            raise UserError(f"Failed to get WiFi networks: {str(e)}")

    def get_firewall_rules(self, site_id=None):
        """Get all firewall rules for a site."""
        site = site_id or self.site_id
        if self.is_udm:
            # For UDM Pro, use the network proxy endpoint
            return self._api_request('GET', f'proxy/network/api/s/{site}/firewallrule')
        return self._api_request('GET', f'api/s/{site}/rest/firewallrule')

    def get_port_forward_rules(self, site_id=None):
        """Get all port forwarding rules for a site."""
        site = site_id or self.site_id
        _logger.info("Trying port forward rules endpoint")
        if self.is_udm:
            # For UDM Pro, use the network proxy endpoint
            return self._api_request('GET', f'proxy/network/api/s/{site}/rest/portforward')
        return self._api_request('GET', f'api/s/{site}/rest/portforward')