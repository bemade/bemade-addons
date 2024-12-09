from .unifi_client import Unifi

from odoo import models, fields, api
from odoo.exceptions import ValidationError
#from unificontrol import UnifiClient


class UnifiCtrl(models.Model):
    _name = 'unifi.ctrl'
    _description = 'Unifi Controller'

    name = fields.Char(
        string='Name', 
        required=True
        )

    ip_address = fields.Char(
        string='IP Address', 
        required=True, 
        help="IP address of the Unifi Controller."
        )

    api_port = fields.Integer(
        string='API Port', 
        default=8443, 
        help="Port used for the Unifi API."
        )

    username = fields.Char(
        string='Username', 
        required=True, 
        help="Username for API authentication."
        )

    password = fields.Char(
        string='Password', 
        required=True, 
        help="Password for API authentication."
        )

    def action_test_connection(self):
        """Test connection to Unifi Controller."""
        self.ensure_one()
        client = Unifi(self.ip_address, self.username, self.password)
        try:
            client.login()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Connection successful!',
                    'type': 'success',
                },
            }
        except Exception as e:
            raise ValidationError(f"Connection failed: {e}")