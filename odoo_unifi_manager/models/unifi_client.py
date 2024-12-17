import requests
import urllib3
from odoo.exceptions import ValidationError

# API Endpoints
UNIFI_LOGIN_PATH = '/api/auth/login'
UNIFI_SITES_PATH = '/api/self/sites'
UNIFI_FIREWALL_RULES_PATH = '/api/s/default/rest/firewallrule'
UNIFI_NETWORKS_PATH = '/api/s/default/rest/network'
UNIFI_WIFIS_PATH = '/api/s/default/rest/wlanconf'

# Prefix for UDM Pro endpoints
UDM_PROXY_PREFIX = '/proxy/network'

# Disable SSL verification warnings
urllib3.disable_warnings()


class Unifi:
    def __init__(self, host, username, password, is_udm=False):
        """Initialize Unifi client."""
        self.host = host
        self.username = username
        self.password = password
        self.is_udm = is_udm
        self.session = requests.Session()
        self.csrf = ""

    def _get_url(self, path):
        """Construct the correct URL based on the type of controller."""
        prefix = UDM_PROXY_PREFIX if self.is_udm else ""
        return f"https://{self.host}{prefix}{path}"

    def login(self):
        """Authenticate with the Unifi Controller or UDM Pro."""
        payload = {
            "username": self.username,
            "password": self.password,
        }
        try:
            r = self.request(UNIFI_LOGIN_PATH, payload)
            if r.ok:
                return True
            else:
                raise ValidationError(f"Login failed: {r.text}")
        except requests.RequestException as e:
            raise ValidationError(f"Failed to connect to Unifi Controller: {e}")

    def request(self, path, data=None, method='POST'):
        """Send a request to the Unifi API."""
        if data is None:
            data = {}
        uri = self._get_url(path)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
        }
        if self.csrf:
            headers["X-CSRF-Token"] = self.csrf
        try:
            r = getattr(self.session, method.lower())(uri, json=data, verify=False, headers=headers)
            if 'X-CSRF-Token' in r.headers:
                self.csrf = r.headers['X-CSRF-Token']
            return r
        except requests.RequestException as e:
            raise ValidationError(f"Request to Unifi Controller failed: {e}")

    def get_sites(self):
        """Retrieve available sites."""
        try:
            r = self.request(UNIFI_SITES_PATH, method='GET')
            if r.ok:
                return r.json().get('data', [])
            else:
                raise ValidationError(f"Failed to retrieve sites: {r.text}")
        except requests.RequestException as e:
            raise ValidationError(f"Failed to retrieve sites: {e}")

    def get_firewall_rules(self):
        """Retrieve all firewall rules."""
        try:
            r = self.request(UNIFI_FIREWALL_RULES_PATH, method='GET')
            if r.ok:
                return r.json().get('data', [])
            else:
                raise ValidationError(f"Failed to retrieve firewall rules: {r.text}")
        except requests.RequestException as e:
            raise ValidationError(f"Request to fetch firewall rules failed: {e}")

    def get_networks(self):
        """Retrieve all networks."""
        try:
            r = self.request(UNIFI_NETWORKS_PATH, method='GET')
            if r.ok:
                return r.json().get('data', [])
            else:
                raise ValidationError(f"Failed to retrieve networks: {r.text}")
        except requests.RequestException as e:
            raise ValidationError(f"Request to fetch networks failed: {e}")

    def get_wifis(self):
        """Retrieve all WiFi configurations."""
        try:
            r = self.request(UNIFI_WIFIS_PATH, method='GET')
            if r.ok:
                return r.json().get('data', [])
            else:
                raise ValidationError(f"Failed to retrieve WiFi configurations: {r.text}")
        except requests.RequestException as e:
            raise ValidationError(f"Request to fetch WiFi configurations failed: {e}")