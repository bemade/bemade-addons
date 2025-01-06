from odoo import models, fields, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class Wifi(models.Model):
    _name = 'unifi.wifi'
    _description = 'Unifi WiFi Network'

    name = fields.Char(string='WiFi Name (SSID)', required=True)
    unifi_id = fields.Char(string='UniFi ID', readonly=True)
    last_sync = fields.Datetime(string='Last Synchronization', readonly=True)
    
    security_mode = fields.Selection(
        [('open', 'Open'), ('wpa', 'WPA/WPA2 Personal'), ('wpa3', 'WPA3')],
        string='Security Mode', 
        required=True,
        default='wpa'
    )

    password = fields.Char(
        string='WiFi Password', 
        help="Password for the WiFi network (if applicable)."
    )

    vlan_id = fields.Many2one(
        comodel_name='unifi.network',
        string='VLAN'
    )

    description = fields.Text(
        string='Description'
    )

    ctrl_id = fields.Many2one(
        'unifi.ctrl', 
        string='Controller', 
        required=True, 
        help="Controller where this rule is applied."
    )

    @api.model
    def sync_from_controller(self, client, controller_id):
        """Synchronize WiFi networks from UniFi Controller."""
        try:
            _logger.info(f"Starting WiFi sync for controller {controller_id}")
            wifi_configs = client.get_wifis()
            synced_ids = []
            
            for wifi in wifi_configs:
                # Map security mode
                security = wifi.get('security', '').lower()
                if 'wpa3' in security:
                    security_mode = 'wpa3'
                elif 'wpa' in security:
                    security_mode = 'wpa'
                else:
                    security_mode = 'open'
                
                values = {
                    'name': wifi.get('name', ''),
                    'unifi_id': wifi.get('_id', ''),
                    'security_mode': security_mode,
                    'password': wifi.get('x_passphrase', ''),  # Note: This might be encrypted
                    'description': wifi.get('name_combine', '') or wifi.get('name', ''),
                    'last_sync': fields.Datetime.now(),
                    'ctrl_id': controller_id,
                }
                
                # Try to find VLAN if specified
                vlan_id = wifi.get('vlan_id')
                if vlan_id:
                    network = self.env['unifi.network'].search([
                        ('ctrl_id', '=', controller_id),
                        ('vlan', '=', vlan_id)
                    ], limit=1)
                    if network:
                        values['vlan_id'] = network.id
                
                # Update existing or create new
                existing = self.search([
                    ('unifi_id', '=', values['unifi_id']),
                    ('ctrl_id', '=', controller_id)
                ])
                
                if existing:
                    _logger.info(f"Updating existing WiFi network: {values['name']}")
                    existing.write(values)
                else:
                    _logger.info(f"Creating new WiFi network: {values['name']}")
                    self.create(values)
                
                synced_ids.append(values['unifi_id'])
            
            # Disable WiFi networks that no longer exist in the controller
            outdated = self.search([
                ('ctrl_id', '=', controller_id),
                ('unifi_id', 'not in', synced_ids)
            ])
            if outdated:
                _logger.info(f"Disabling {len(outdated)} outdated WiFi networks")
                outdated.unlink()
            
            _logger.info("WiFi synchronization completed successfully")
            
        except Exception as e:
            _logger.error(f"Error during WiFi synchronization: {str(e)}")
            raise api.UserError(f"Failed to sync WiFi networks: {str(e)}")

    def sync_to_controller(self):
        """Synchronize WiFi network to UniFi Controller."""
        self.ensure_one()
        client = self.ctrl_id.get_client()
        # Implementation of pushing changes to UniFi
        # This would need to be implemented based on UniFi's API
        pass
