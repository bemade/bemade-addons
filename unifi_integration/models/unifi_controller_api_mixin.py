# -*- coding: utf-8 -*-

# These imports will work in an Odoo environment, even if your IDE marks them as not found
# pylint: disable=import-error
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
# pylint: enable=import-error

import json
import logging
import requests
import urllib3
import tempfile
import os
import base64
from datetime import datetime, timedelta
from typing import Dict, Tuple, List, Any
from requests.exceptions import RequestException, ConnectionError

_logger = logging.getLogger(__name__)

class UnifiControllerAPIMixin(models.AbstractModel):
    """Mixin for UniFi Controller API specific functionality
    
    This mixin provides methods and functionality specific to the UniFi Controller API.
    It is used by the UnifiSite model when api_type is 'controller'.
    """
    _name = 'unifi.controller.api.mixin'
    _description = 'UniFi Controller API Functionality Mixin'
    
    def _test_controller_connection(self, site, api_log=None):
        """Test connection to the UniFi Controller
        
        Args:
            site: UnifiSite record to test connection for
            api_log: Optional API log record to update with results
            
        Returns:
            dict: Dictionary with connection test results
        """
        if not site.host or not site.port or not site.username or not site.password:
            error_msg = _("Missing connection parameters. Please provide host, port, username, and password.")
            if api_log:
                site._update_api_log(api_log, {
                    'status': 'error',
                    'message': error_msg,
                    'response_code': 0,
                    'response_time': 0,
                })
            return {
                'success': False,
                'message': error_msg,
                'details': {},
            }
        
        # Disable SSL warnings if verify_ssl is False
        if not site.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Prepare the login URL based on controller type
        controller_type = site.controller_type if hasattr(site, 'controller_type') else 'standard'
        
        if controller_type == 'udm':
            # UDM Pro/UCG Max uses a different login endpoint
            _logger.debug("Utilisation de l'endpoint d'authentification UDM Pro/UCG Max")
            login_endpoint = f"https://{site.host}:{site.port}/api/auth/login"
        else:
            # Standard controller
            _logger.debug("Utilisation de l'endpoint d'authentification standard")
            login_endpoint = f"https://{site.host}:{site.port}/api/login"
            
        _logger.debug("Endpoint d'authentification utilisé: %s", login_endpoint)
        
        # Prepare the login payload
        login_payload = {
            'username': site.username,
            'password': site.password,
            'remember': True,
        }
        
        # Prepare SSL verification
        ssl_verify = site.verify_ssl
        if site.ssl_cert_path and os.path.exists(site.ssl_cert_path):
            ssl_verify = site.ssl_cert_path
        
        # Start timing the request
        start_time = datetime.now()
        
        try:
            # Make the login request
            response = requests.post(
                login_endpoint,
                json=login_payload,
                verify=ssl_verify,
                timeout=site.timeout,
            )
            
            # Calculate response time
            response_time = (datetime.now() - start_time).total_seconds()
            
            # Check if the login was successful
            if response.status_code == 200:
                # Extract cookies from the response
                cookies = response.cookies
                
                # Create or update the authentication session
                site._create_auth_session(cookies, login_endpoint)
                
                # Update the API log if provided
                if api_log:
                    site._update_api_log(api_log, {
                        'status': 'success',
                        'message': _("Successfully connected to UniFi Controller"),
                        'response_code': response.status_code,
                        'response_time': response_time,
                        'request_headers': str(response.request.headers),
                        'response_headers': str(response.headers),
                        'response_content': response.text,
                    })
                
                # Return success
                return {
                    'success': True,
                    'message': _("Successfully connected to UniFi Controller"),
                    'details': {
                        'status_code': response.status_code,
                        'response_time': response_time,
                        'cookies': {k: v for k, v in cookies.items()},
                    },
                }
            else:
                # Login failed
                error_msg = _("Failed to connect to UniFi Controller. Status code: %s") % response.status_code
                
                # Update the API log if provided
                if api_log:
                    site._update_api_log(api_log, {
                        'status': 'error',
                        'message': error_msg,
                        'response_code': response.status_code,
                        'response_time': response_time,
                        'request_headers': str(response.request.headers),
                        'response_headers': str(response.headers),
                        'response_content': response.text,
                    })
                
                # Return failure
                return {
                    'success': False,
                    'message': error_msg,
                    'details': {
                        'status_code': response.status_code,
                        'response_time': response_time,
                        'response_text': response.text,
                    },
                }
        
        except (RequestException, ConnectionError) as e:
            # Handle connection errors
            error_msg = _("Connection error: %s") % str(e)
            
            # Update the API log if provided
            if api_log:
                site._update_api_log(api_log, {
                    'status': 'error',
                    'message': error_msg,
                    'response_code': 0,
                    'response_time': (datetime.now() - start_time).total_seconds(),
                })
            
            # Return failure
            return {
                'success': False,
                'message': error_msg,
                'details': {
                    'exception': str(e),
                },
            }
    
    def _get_controller_device_data(self, site):
        """Get device data from the UniFi Controller
        
        Args:
            site: UnifiSite record to get device data for
            
        Returns:
            list: List of device data dictionaries or False on failure
        """
        # Check if we have a valid authentication session
        if not site._check_auth_session():
            return False
        
        # Prepare the API endpoint
        endpoint = f"https://{site.host}:{site.port}/api/s/{site.site_id}/stat/device"
        
        # Prepare SSL verification
        ssl_verify = site.verify_ssl
        if site.ssl_cert_path and os.path.exists(site.ssl_cert_path):
            ssl_verify = site.ssl_cert_path
        
        # Get authentication cookies
        cookies = site._get_auth_cookies()
        if not cookies:
            return False
        
        # Create an API log entry
        api_log = site._create_api_log(
            api_method='get_device_data',
            message_text=_("Retrieving device data from UniFi Controller"),
            direction='outbound'
        )
        
        try:
            # Make the API request
            response = requests.get(
                endpoint,
                cookies=cookies,
                verify=ssl_verify,
                timeout=site.timeout,
            )
            
            # Update the API log
            site._update_api_log(api_log, {
                'request_url': endpoint,
                'request_method': 'GET',
                'request_headers': str(response.request.headers),
                'response_headers': str(response.headers),
                'response_content': response.text,
                'response_code': response.status_code,
                'response_time': 0,  # We're not tracking time here
            })
            
            # Check if the request was successful
            if response.status_code == 200:
                # Parse the response
                data = response.json()
                
                # Check if the response contains data
                if 'data' in data and isinstance(data['data'], list):
                    # Update the API log
                    site._update_api_log(api_log, {
                        'status': 'success',
                        'message': _("Successfully retrieved device data"),
                    })
                    
                    # Return the device data
                    return data['data']
                else:
                    # No data in the response
                    site._update_api_log(api_log, {
                        'status': 'error',
                        'message': _("No device data found in the response"),
                    })
                    return []
            else:
                # Request failed
                site._update_api_log(api_log, {
                    'status': 'error',
                    'message': _("Failed to retrieve device data. Status code: %s") % response.status_code,
                })
                return False
        
        except (RequestException, ConnectionError, ValueError, json.JSONDecodeError) as e:
            # Handle errors
            site._update_api_log(api_log, {
                'status': 'error',
                'message': _("Error retrieving device data: %s") % str(e),
            })
            return False
    
    def _get_controller_network_data(self, site):
        """Get network data from the UniFi Controller
        
        Args:
            site: UnifiSite record to get network data for
            
        Returns:
            list: List of network data dictionaries or False on failure
        """
        # Check if we have a valid authentication session
        if not site._check_auth_session():
            return False
        
        # Prepare the API endpoint
        # Déterminer si c'est un UDM Pro/UCG Max ou un contrôleur standard
        # Les UDM Pro/UCG Max nécessitent le préfixe /proxy/network
        controller_type = site.controller_type if hasattr(site, 'controller_type') else 'standard'
        
        if controller_type == 'udm':
            _logger.debug("Utilisation de l'endpoint UDM Pro/UCG Max pour récupérer les réseaux")
            endpoint = f"https://{site.host}:{site.port}/proxy/network/api/s/{site.site_id}/rest/networkconf"
        else:
            _logger.debug("Utilisation de l'endpoint contrôleur standard pour récupérer les réseaux")
            endpoint = f"https://{site.host}:{site.port}/api/s/{site.site_id}/rest/networkconf"
        
        _logger.debug("Endpoint utilisé: %s", endpoint)
        
        # Prepare SSL verification
        ssl_verify = site.verify_ssl
        if site.ssl_cert_path and os.path.exists(site.ssl_cert_path):
            ssl_verify = site.ssl_cert_path
        
        # Get authentication cookies
        cookies = site._get_auth_cookies()
        if not cookies:
            return False
        
        # Create an API log entry
        api_log = site._create_api_log(
            api_method='get_network_data',
            message_text=_("Retrieving network data from UniFi Controller"),
            direction='outbound'
        )
        
        try:
            # Make the API request
            response = requests.get(
                endpoint,
                cookies=cookies,
                verify=ssl_verify,
                timeout=site.timeout,
            )
            
            # Update the API log
            site._update_api_log(api_log, {
                'request_url': endpoint,
                'request_method': 'GET',
                'request_headers': str(response.request.headers),
                'response_headers': str(response.headers),
                'response_content': response.text,
                'response_code': response.status_code,
                'response_time': 0,  # We're not tracking time here
            })
            
            # Check if the request was successful
            if response.status_code == 200:
                # Parse the response
                data = response.json()
                
                # Check if the response contains data
                if 'data' in data and isinstance(data['data'], list):
                    # Update the API log
                    site._update_api_log(api_log, {
                        'status': 'success',
                        'message': _("Successfully retrieved network data"),
                    })
                    
                    # Return the network data
                    return data['data']
                else:
                    # No data in the response
                    site._update_api_log(api_log, {
                        'status': 'error',
                        'message': _("No network data found in the response"),
                    })
                    return []
            else:
                # Request failed
                site._update_api_log(api_log, {
                    'status': 'error',
                    'message': _("Failed to retrieve network data. Status code: %s") % response.status_code,
                })
                return False
        
        except (RequestException, ConnectionError, ValueError, json.JSONDecodeError) as e:
            # Handle errors
            site._update_api_log(api_log, {
                'status': 'error',
                'message': _("Error retrieving network data: %s") % str(e),
            })
            return False
    
    def _get_controller_vlan_data(self, site):
        """Get VLAN data from the UniFi Controller
        
        Args:
            site: UnifiSite record to get VLAN data for
            
        Returns:
            list: List of VLAN data dictionaries or False on failure
        """
        # Check if we have a valid authentication session
        if not site._check_auth_session():
            return False
        
        # Prepare the API endpoint
        endpoint = f"https://{site.host}:{site.port}/api/s/{site.site_id}/rest/vlan"
        
        # Prepare SSL verification
        ssl_verify = site.verify_ssl
        if site.ssl_cert_path and os.path.exists(site.ssl_cert_path):
            ssl_verify = site.ssl_cert_path
        
        # Get authentication cookies
        cookies = site._get_auth_cookies()
        if not cookies:
            return False
        
        # Create an API log entry
        api_log = site._create_api_log(
            api_method='get_vlan_data',
            message_text=_("Retrieving VLAN data from UniFi Controller"),
            direction='outbound'
        )
        
        try:
            # Make the API request
            response = requests.get(
                endpoint,
                cookies=cookies,
                verify=ssl_verify,
                timeout=site.timeout,
            )
            
            # Update the API log
            site._update_api_log(api_log, {
                'request_url': endpoint,
                'request_method': 'GET',
                'request_headers': str(response.request.headers),
                'response_headers': str(response.headers),
                'response_content': response.text,
                'response_code': response.status_code,
                'response_time': 0,  # We're not tracking time here
            })
            
            # Check if the request was successful
            if response.status_code == 200:
                # Parse the response
                data = response.json()
                
                # Check if the response contains data
                if 'data' in data and isinstance(data['data'], list):
                    # Update the API log
                    site._update_api_log(api_log, {
                        'status': 'success',
                        'message': _("Successfully retrieved VLAN data"),
                    })
                    
                    # Return the VLAN data
                    return data['data']
                else:
                    # No data in the response
                    site._update_api_log(api_log, {
                        'status': 'error',
                        'message': _("No VLAN data found in the response"),
                    })
                    return []
            else:
                # Request failed
                site._update_api_log(api_log, {
                    'status': 'error',
                    'message': _("Failed to retrieve VLAN data. Status code: %s") % response.status_code,
                })
                return False
        
        except (RequestException, ConnectionError, ValueError, json.JSONDecodeError) as e:
            # Handle errors
            site._update_api_log(api_log, {
                'status': 'error',
                'message': _("Error retrieving VLAN data: %s") % str(e),
            })
            return False
    
    def _get_controller_user_data(self, site):
        """Get user data from the UniFi Controller
        
        Args:
            site: UnifiSite record to get user data for
            
        Returns:
            list: List of user data dictionaries or False on failure
        """
        # Check if we have a valid authentication session
        if not site._check_auth_session():
            return False
        
        # Prepare the API endpoint
        endpoint = f"https://{site.host}:{site.port}/api/s/{site.site_id}/stat/sta"
        
        # Prepare SSL verification
        ssl_verify = site.verify_ssl
        if site.ssl_cert_path and os.path.exists(site.ssl_cert_path):
            ssl_verify = site.ssl_cert_path
        
        # Get authentication cookies
        cookies = site._get_auth_cookies()
        if not cookies:
            return False
        
        # Create an API log entry
        api_log = site._create_api_log(
            api_method='get_user_data',
            message_text=_("Retrieving user data from UniFi Controller"),
            direction='outbound'
        )
        
        try:
            # Make the API request
            response = requests.get(
                endpoint,
                cookies=cookies,
                verify=ssl_verify,
                timeout=site.timeout,
            )
            
            # Update the API log
            site._update_api_log(api_log, {
                'request_url': endpoint,
                'request_method': 'GET',
                'request_headers': str(response.request.headers),
                'response_headers': str(response.headers),
                'response_content': response.text,
                'response_code': response.status_code,
                'response_time': 0,  # We're not tracking time here
            })
            
            # Check if the request was successful
            if response.status_code == 200:
                # Parse the response
                data = response.json()
                
                # Check if the response contains data
                if 'data' in data and isinstance(data['data'], list):
                    # Update the API log
                    site._update_api_log(api_log, {
                        'status': 'success',
                        'message': _("Successfully retrieved user data"),
                    })
                    
                    # Return the user data
                    return data['data']
                else:
                    # No data in the response
                    site._update_api_log(api_log, {
                        'status': 'error',
                        'message': _("No user data found in the response"),
                    })
                    return []
            else:
                # Request failed
                site._update_api_log(api_log, {
                    'status': 'error',
                    'message': _("Failed to retrieve user data. Status code: %s") % response.status_code,
                })
                return False
        
        except (RequestException, ConnectionError, ValueError, json.JSONDecodeError) as e:
            # Handle errors
            site._update_api_log(api_log, {
                'status': 'error',
                'message': _("Error retrieving user data: %s") % str(e),
            })
            return False
    
    def _get_controller_firewall_data(self, site):
        """Get firewall rule data from the UniFi Controller
        
        Args:
            site: UnifiSite record to get firewall rule data for
            
        Returns:
            list: List of firewall rule data dictionaries or False on failure
        """
        # Check if we have a valid authentication session
        if not site._check_auth_session():
            return False
        
        # Prepare the API endpoint
        endpoint = f"https://{site.host}:{site.port}/api/s/{site.site_id}/rest/firewallrule"
        
        # Prepare SSL verification
        ssl_verify = site.verify_ssl
        if site.ssl_cert_path and os.path.exists(site.ssl_cert_path):
            ssl_verify = site.ssl_cert_path
        
        # Get authentication cookies
        cookies = site._get_auth_cookies()
        if not cookies:
            return False
        
        # Create an API log entry
        api_log = site._create_api_log(
            api_method='get_firewall_data',
            message_text=_("Retrieving firewall rule data from UniFi Controller"),
            direction='outbound'
        )
        
        try:
            # Make the API request
            response = requests.get(
                endpoint,
                cookies=cookies,
                verify=ssl_verify,
                timeout=site.timeout,
            )
            
            # Update the API log
            site._update_api_log(api_log, {
                'request_url': endpoint,
                'request_method': 'GET',
                'request_headers': str(response.request.headers),
                'response_headers': str(response.headers),
                'response_content': response.text,
                'response_code': response.status_code,
                'response_time': 0,  # We're not tracking time here
            })
            
            # Check if the request was successful
            if response.status_code == 200:
                # Parse the response
                data = response.json()
                
                # Check if the response contains data
                if 'data' in data and isinstance(data['data'], list):
                    # Update the API log
                    site._update_api_log(api_log, {
                        'status': 'success',
                        'message': _("Successfully retrieved firewall rule data"),
                    })
                    
                    # Return the firewall rule data
                    return data['data']
                else:
                    # No data in the response
                    site._update_api_log(api_log, {
                        'status': 'error',
                        'message': _("No firewall rule data found in the response"),
                    })
                    return []
            else:
                # Request failed
                site._update_api_log(api_log, {
                    'status': 'error',
                    'message': _("Failed to retrieve firewall rule data. Status code: %s") % response.status_code,
                })
                return False
        
        except (RequestException, ConnectionError, ValueError, json.JSONDecodeError) as e:
            # Handle errors
            site._update_api_log(api_log, {
                'status': 'error',
                'message': _("Error retrieving firewall rule data: %s") % str(e),
            })
            return False
    
    def _sync_controller_devices(self, site):
        """Synchronize devices from the UniFi Controller
        
        Args:
            site: UnifiSite record to synchronize devices for
            
        Returns:
            dict: Dictionary with synchronization results
        """
        # Get device data
        device_data = self._get_controller_device_data(site)
        if not device_data:
            return {
                'success': False,
                'message': _("Failed to retrieve device data"),
                'details': {},
            }
        
        # Create a counter for statistics
        stats = {
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
        }
        
        # Process each device
        for device in device_data:
            try:
                # Check if the device already exists
                existing_device = site.env['unifi.device'].search([
                    ('site_id', '=', site.id),
                    ('mac_address', '=', device.get('mac')),
                ], limit=1)
                
                # Prepare device values
                device_vals = {
                    'site_id': site.id,
                    'mac_address': device.get('mac'),
                    'name': device.get('name') or device.get('model'),
                    'model': device.get('model'),
                    'ip_address': device.get('ip'),
                    'device_type': device.get('type'),
                    'firmware_version': device.get('version'),
                    'last_seen': fields.Datetime.now(),
                    'raw_data': json.dumps(device),
                    'active': True,
                }
                
                if existing_device:
                    # Update existing device
                    existing_device.write(device_vals)
                    stats['updated'] += 1
                else:
                    # Create new device
                    site.env['unifi.device'].create(device_vals)
                    stats['created'] += 1
            
            except Exception as e:
                _logger.error("Error processing device %s: %s", device.get('mac'), str(e))
                stats['errors'] += 1
        
        # Return the results
        return {
            'success': True,
            'message': _("Successfully synchronized devices"),
            'details': {
                'count': len(device_data),
                'stats': stats,
            },
        }
    
    def _sync_controller_networks(self, site):
        """Synchronize networks from the UniFi Controller
        
        Args:
            site: UnifiSite record to synchronize networks for
            
        Returns:
            dict: Dictionary with synchronization results
        """
        # Get network data
        network_data = self._get_controller_network_data(site)
        if not network_data:
            return {
                'success': False,
                'message': _("Failed to retrieve network data"),
                'details': {},
            }
        
        # Create a counter for statistics
        stats = {
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
        }
        
        # Process each network
        for network in network_data:
            try:
                # Check if the network already exists
                existing_network = site.env['unifi.network'].search([
                    ('site_id', '=', site.id),
                    ('network_id', '=', network.get('_id')),
                ], limit=1)
                
                # Prepare network values
                network_vals = {
                    'site_id': site.id,
                    'network_id': network.get('_id'),
                    'name': network.get('name'),
                    'purpose': network.get('purpose'),
                    'subnet': network.get('ip_subnet'),
                    'vlan_id': network.get('vlan_id'),
                    'dhcp_enabled': network.get('dhcp_enabled', False),
                    'dhcp_start': network.get('dhcp_start'),
                    'dhcp_stop': network.get('dhcp_stop'),
                    'domain_name': network.get('domain_name'),
                    'raw_data': json.dumps(network),
                    'active': True,
                }
                
                if existing_network:
                    # Update existing network
                    existing_network.write(network_vals)
                    stats['updated'] += 1
                else:
                    # Create new network
                    site.env['unifi.network'].create(network_vals)
                    stats['created'] += 1
            
            except Exception as e:
                _logger.error("Error processing network %s: %s", network.get('_id'), str(e))
                stats['errors'] += 1
        
        # Return the results
        return {
            'success': True,
            'message': _("Successfully synchronized networks"),
            'details': {
                'count': len(network_data),
                'stats': stats,
            },
        }