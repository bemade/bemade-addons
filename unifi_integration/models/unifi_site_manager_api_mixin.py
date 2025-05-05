# -*- coding: utf-8 -*-

# These imports will work in an Odoo environment, even if your IDE marks them as not found
# pylint: disable=import-error
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
# pylint: enable=import-error

import json
import logging
import requests
from typing import Dict, Any, List, Optional
from requests.exceptions import RequestException, ConnectionError

_logger = logging.getLogger(__name__)

class UnifiSiteManagerAPIMixin(models.AbstractModel):
    """Mixin for UniFi Site Manager API specific functionality
    
    This mixin provides methods and functionality specific to the UniFi Site Manager API.
    It is used by the UnifiSite model when api_type is 'site_manager'.
    """
    _name = 'unifi.site.manager.api.mixin'
    _description = 'UniFi Site Manager API Functionality Mixin'
    
    def _test_site_manager_connection(self, site, api_log=None):
        """Test connection to the UniFi Site Manager API
        
        Args:
            site: UnifiSite record to test connection for
            api_log: Optional API log record to update with results
            
        Returns:
            dict: Dictionary with connection test results
        """
        # Check if API key is provided
        if not site.api_key:
            error_msg = _("Missing API key. Please provide an API key for Site Manager authentication.")
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
        
        # Prepare the API endpoint
        endpoint = "https://unifi.ui.com/api/sitemgr/v1/site"
        
        # Prepare headers with API key
        headers = {
            'Authorization': f'Bearer {site.api_key}',
            'Content-Type': 'application/json',
        }
        
        # Add MFA token if enabled
        if site.mfa_enabled and site.mfa_token:
            headers['X-MFA-Token'] = site.mfa_token
        
        try:
            # Make the API request
            response = requests.get(
                endpoint,
                headers=headers,
                verify=site.verify_ssl,
                timeout=site.timeout,
            )
            
            # Check if the request was successful
            if response.status_code == 200:
                # Parse the response
                data = response.json()
                
                # Update the API log if provided
                if api_log:
                    site._update_api_log(api_log, {
                        'status': 'success',
                        'message': _("Successfully connected to UniFi Site Manager API"),
                        'response_code': response.status_code,
                        'response_time': 0,  # We're not tracking time here
                        'request_headers': str(headers),
                        'response_headers': str(response.headers),
                        'response_content': response.text,
                    })
                
                # Return success
                return {
                    'success': True,
                    'message': _("Successfully connected to UniFi Site Manager API"),
                    'details': {
                        'status_code': response.status_code,
                        'data': data,
                    },
                }
            else:
                # Request failed
                error_msg = _("Failed to connect to UniFi Site Manager API. Status code: %s") % response.status_code
                
                # Update the API log if provided
                if api_log:
                    site._update_api_log(api_log, {
                        'status': 'error',
                        'message': error_msg,
                        'response_code': response.status_code,
                        'response_time': 0,  # We're not tracking time here
                        'request_headers': str(headers),
                        'response_headers': str(response.headers),
                        'response_content': response.text,
                    })
                
                # Return failure
                return {
                    'success': False,
                    'message': error_msg,
                    'details': {
                        'status_code': response.status_code,
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
                    'response_time': 0,
                })
            
            # Return failure
            return {
                'success': False,
                'message': error_msg,
                'details': {
                    'exception': str(e),
                },
            }
    
    def _get_site_manager_device_data(self, site):
        """Get device data from the UniFi Site Manager API
        
        Args:
            site: UnifiSite record to get device data for
            
        Returns:
            list: List of device data dictionaries or False on failure
        """
        # Prepare the API endpoint
        endpoint = f"https://unifi.ui.com/api/sitemgr/v1/site/{site.site_id}/device"
        
        # Prepare headers with API key
        headers = {
            'Authorization': f'Bearer {site.api_key}',
            'Content-Type': 'application/json',
        }
        
        # Add MFA token if enabled
        if site.mfa_enabled and site.mfa_token:
            headers['X-MFA-Token'] = site.mfa_token
        
        # Create an API log entry
        api_log = site._create_api_log(
            api_method='get_device_data',
            message_text=_("Retrieving device data from UniFi Site Manager API"),
            direction='outbound'
        )
        
        try:
            # Make the API request
            response = requests.get(
                endpoint,
                headers=headers,
                verify=site.verify_ssl,
                timeout=site.timeout,
            )
            
            # Update the API log
            site._update_api_log(api_log, {
                'request_url': endpoint,
                'request_method': 'GET',
                'request_headers': str(headers),
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
    
    def _get_site_manager_network_data(self, site):
        """Get network data from the UniFi Site Manager API
        
        Args:
            site: UnifiSite record to get network data for
            
        Returns:
            list: List of network data dictionaries or False on failure
        """
        # Prepare the API endpoint
        endpoint = f"https://unifi.ui.com/api/sitemgr/v1/site/{site.site_id}/network"
        
        # Prepare headers with API key
        headers = {
            'Authorization': f'Bearer {site.api_key}',
            'Content-Type': 'application/json',
        }
        
        # Add MFA token if enabled
        if site.mfa_enabled and site.mfa_token:
            headers['X-MFA-Token'] = site.mfa_token
        
        # Create an API log entry
        api_log = site._create_api_log(
            api_method='get_network_data',
            message_text=_("Retrieving network data from UniFi Site Manager API"),
            direction='outbound'
        )
        
        try:
            # Make the API request
            response = requests.get(
                endpoint,
                headers=headers,
                verify=site.verify_ssl,
                timeout=site.timeout,
            )
            
            # Update the API log
            site._update_api_log(api_log, {
                'request_url': endpoint,
                'request_method': 'GET',
                'request_headers': str(headers),
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
    
    def _get_site_manager_vlan_data(self, site):
        """Get VLAN data from the UniFi Site Manager API
        
        Args:
            site: UnifiSite record to get VLAN data for
            
        Returns:
            list: List of VLAN data dictionaries or False on failure
        """
        # Prepare the API endpoint
        endpoint = f"https://unifi.ui.com/api/sitemgr/v1/site/{site.site_id}/vlan"
        
        # Prepare headers with API key
        headers = {
            'Authorization': f'Bearer {site.api_key}',
            'Content-Type': 'application/json',
        }
        
        # Add MFA token if enabled
        if site.mfa_enabled and site.mfa_token:
            headers['X-MFA-Token'] = site.mfa_token
        
        # Create an API log entry
        api_log = site._create_api_log(
            api_method='get_vlan_data',
            message_text=_("Retrieving VLAN data from UniFi Site Manager API"),
            direction='outbound'
        )
        
        try:
            # Make the API request
            response = requests.get(
                endpoint,
                headers=headers,
                verify=site.verify_ssl,
                timeout=site.timeout,
            )
            
            # Update the API log
            site._update_api_log(api_log, {
                'request_url': endpoint,
                'request_method': 'GET',
                'request_headers': str(headers),
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
    
    def _sync_site_manager_devices(self, site):
        """Synchronize devices from the UniFi Site Manager API
        
        Args:
            site: UnifiSite record to synchronize devices for
            
        Returns:
            dict: Dictionary with synchronization results
        """
        # Get device data
        device_data = self._get_site_manager_device_data(site)
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
    
    def _sync_site_manager_networks(self, site):
        """Synchronize networks from the UniFi Site Manager API
        
        Args:
            site: UnifiSite record to synchronize networks for
            
        Returns:
            dict: Dictionary with synchronization results
        """
        # Get network data
        network_data = self._get_site_manager_network_data(site)
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