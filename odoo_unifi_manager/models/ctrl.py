from odoo import models, fields, api
from .unifi_client import Unifi
from odoo.exceptions import ValidationError


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

    controller_type = fields.Selection(
        [
            ('udm', 'UDM Pro'),
            ('controller', 'Controller')
        ],
        string="Controller Type",
        default='udm',
        required=True,
        help="Select whether this is a UDM Pro or a Unifi Controller."
        )

    def action_test_connection(self):
        """Test connection to Unifi Controller or UDM Pro."""
        self.ensure_one()
        client = Unifi(
            host=self.ip_address,
            username=self.username,
            password=self.password,
            is_udm=(self.controller_type == 'udm')
        )
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

    def action_fetch_networks_and_fill_rules(self):
        """Fetch networks and populate firewall rules."""
        self.ensure_one()
        client = Unifi(
            host=self.ip_address,
            username=self.username,
            password=self.password,
            is_udm=(self.controller_type == 'udm')
        )
        try:
            client.login()
            networks = client.get_networks()

            firewall_rule_model = self.env['firewall.rule']
            for network in networks:
                rule_name = network.get('name', 'Unnamed Rule')
                src_ip = network.get('subnet', None)  # Example: Adjust based on API data
                if not src_ip:
                    continue

                firewall_rule_model.create({
                    'name': f"Network: {rule_name}",
                    'action': 'accept',
                    'enabled': True,
                    'src_ip': src_ip,
                    'dst_ip': None,
                    'log': False,
                    'controller_id': self.id,
                })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Networks Fetched',
                    'message': f"{len(networks)} networks fetched and rules created.",
                    'type': 'success',
                },
            }
        except Exception as e:
            raise ValidationError(f"Failed to fetch networks: {e}")