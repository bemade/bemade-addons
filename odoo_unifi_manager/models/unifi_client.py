import requests
import urllib3
from odoo.exceptions import ValidationError

UNIFI_LOGIN_PATH = '/api/auth/login'
UNIFI_SITES_PATH = '/api/self/sites'

# Désactiver les avertissements SSL pour certificats auto-signés
urllib3.disable_warnings()


class Unifi:
    def __init__(self, host, username, password):
        """Initialize Unifi client."""
        self.host = host
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.csrf = ""

    def login(self):
        """Authenticate with the Unifi Controller."""
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
        uri = f'https://{self.host}{path}'
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

    def test_connection(self):
        """Test connection and fetch available sites."""
        if not self.login():
            raise ValidationError("Login failed. Check your credentials.")

        sites = self.get_sites()
        site_list = [site['desc'] for site in sites]
        return f"Connection successful! Available sites: {', '.join(site_list)}"