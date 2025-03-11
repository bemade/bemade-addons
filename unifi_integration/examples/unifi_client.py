"""
UniFi UDM Pro API Client
This module provides a client to interact with the UniFi Dream Machine Pro API.
"""
import os
import json
import requests
from urllib3.exceptions import InsecureRequestWarning
import dotenv

# Suppress only the single warning from urllib3 needed.
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

class UnifiClient:
    """
    A client for interacting with the UniFi Dream Machine Pro API.
    Handles authentication and basic API operations.
    """
    def __init__(self, config_file=None):
        """
        Initialize the UniFi client with configuration from environment file.
        
        Args:
            config_file (str): Path to the configuration file (default: Doc/credential.txt)
        """
        if config_file is None:
            config_file = os.path.join(os.path.dirname(__file__), 'Doc/credential.txt')
        
        # Load configuration from file
        dotenv.load_dotenv(config_file)
        
        self.host = os.getenv('UDMP_HOST').rstrip('/')
        self.username = os.getenv('UDMP_USERNAME')
        self.password = os.getenv('UDMP_PASSWORD')
        self.verify_ssl = os.getenv('VERIFY_SSL', 'false').lower() == 'true'
        
        self.session = requests.Session()
        self.session.verify = self.verify_ssl
        self.csrf_token = None
        
    def login(self):
        """
        Authenticate with the UDM Pro.
        
        Returns:
            bool: True if login successful, False otherwise
        """
        login_url = f"{self.host}/api/auth/login"
        headers = {'Content-Type': 'application/json'}
        data = {
            'username': self.username,
            'password': self.password
        }
        
        try:
            response = self.session.post(
                login_url,
                headers=headers,
                json=data,
                timeout=10  # 10 seconds timeout
            )
            response.raise_for_status()
            
            # Store CSRF token if present
            if 'X-CSRF-Token' in response.headers:
                self.csrf_token = response.headers['X-CSRF-Token']
            
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Login failed: {str(e)}")
            return False
            
    def get_system_info(self):
        """
        Get basic system information.
        
        Returns:
            dict: System information or None if request fails
        """
        url = f"{self.host}/proxy/network/api/s/default/self"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to get system info: {str(e)}")
            return None
            
    def logout(self):
        """
        Logout from the UDM Pro.
        
        Returns:
            bool: True if logout successful, False otherwise
        """
        logout_url = f"{self.host}/api/auth/logout"
        
        # Add required headers for logout
        headers = {
            'Content-Type': 'application/json',
        }
        if self.csrf_token:
            headers['X-CSRF-Token'] = self.csrf_token
        
        try:
            # Send empty JSON body as required by the API
            response = self.session.post(logout_url, headers=headers, json={}, timeout=10)
            
            # Note: UDM Pro returns 200 even if session is already expired
            if response.status_code == 200:
                return True
                
            response.raise_for_status()
            return True
            
        except requests.exceptions.RequestException as e:
            # If we get a 403, it might mean we're already logged out
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 403:
                return True
                
            print(f"Logout failed: {str(e)}")
            return False

    def __enter__(self):
        """Context manager entry point"""
        self.login()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point"""
        self.logout()
        
    def get_devices(self):
        """Get all devices connected to the UDM Pro.
        
        Returns:
            dict: List of devices or None if request fails
        """
        url = f"{self.host}/proxy/network/api/s/default/stat/device"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to get devices: {str(e)}")
            return None
            
    def get_clients(self):
        """Get all clients (users) connected to the network.
        
        Returns:
            dict: List of clients or None if request fails
        """
        url = f"{self.host}/proxy/network/api/s/default/stat/sta"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to get clients: {str(e)}")
            return None
            
    def get_health(self):
        """Get the health status of the UDM Pro and network.
        
        Returns:
            dict: Health information or None if request fails
        """
        url = f"{self.host}/proxy/network/api/s/default/stat/health"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to get health status: {str(e)}")
            return None
            
    def get_firewall_rules(self):
        """Get all firewall rules.
        
        Returns:
            dict: List of firewall rules or None if request fails
        """
        url = f"{self.host}/proxy/network/api/s/default/rest/firewallrule"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to get firewall rules: {str(e)}")
            return None
            
    def get_firewall_groups(self):
        """Get all firewall groups (address groups, port groups).
        
        Returns:
            dict: List of firewall groups or None if request fails
        """
        url = f"{self.host}/proxy/network/api/s/default/rest/firewallgroup"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to get firewall groups: {str(e)}")
            return None
            
    def create_firewall_rule(self, rule_data):
        """Create a new firewall rule.
        
        Args:
            rule_data (dict): Rule configuration with the following fields:
                - name: Rule name
                - action: 'accept' or 'drop' or 'reject'
                - ruleset: 'WAN_IN', 'WAN_OUT', 'WAN_LOCAL', 'LAN_IN', etc.
                - protocol: 'all', 'tcp', 'udp', etc.
                - src_address: Source address/network (optional)
                - dst_address: Destination address/network (optional)
                - src_port: Source port (optional)
                - dst_port: Destination port (optional)
                - enabled: True/False
                
        Returns:
            dict: Created rule data or None if request fails
        """
        url = f"{self.host}/proxy/network/api/s/default/rest/firewallrule"
        
        try:
            response = self.session.post(url, json=rule_data, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to create firewall rule: {str(e)}")
            return None
            
    def update_firewall_rule(self, rule_id, rule_data):
        """Update an existing firewall rule.
        
        Args:
            rule_id (str): ID of the rule to update
            rule_data (dict): Updated rule configuration
                
        Returns:
            dict: Updated rule data or None if request fails
        """
        url = f"{self.host}/proxy/network/api/s/default/rest/firewallrule/{rule_id}"
        
        try:
            response = self.session.put(url, json=rule_data, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to update firewall rule: {str(e)}")
            return None
            
    def delete_firewall_rule(self, rule_id):
        """Delete a firewall rule.
        
        Args:
            rule_id (str): ID of the rule to delete
                
        Returns:
            bool: True if successful, False otherwise
        """
        url = f"{self.host}/proxy/network/api/s/default/rest/firewallrule/{rule_id}"
        
        try:
            response = self.session.delete(url, timeout=10)
            response.raise_for_status()
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to delete firewall rule: {str(e)}")
            return False
            
    def get_networks(self):
        """Get all networks configuration.
        
        Returns:
            dict: List of networks or None if request fails
        """
        url = f"{self.host}/proxy/network/api/s/default/rest/networkconf"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to get networks: {str(e)}")
            return None
