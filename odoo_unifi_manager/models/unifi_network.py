from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re
from datetime import datetime

class Network(models.Model):
    _name = 'unifi.network'
    _description = 'Unifi Network'

    name = fields.Char(
        string='Network Name',
        required=True
    )

    unifi_id = fields.Char(
        string='UniFi ID',
        readonly=True
    )

    last_sync = fields.Datetime(
        string='Last Synchronization',
        readonly=True
    )

    cidr = fields.Char(
        string='CIDR', 
        help="CIDR notation for the network (e.g., 192.168.1.0/24)."
    )

    gateway = fields.Char(
        string='Gateway', 
        help="Gateway IP address for the network."
    )

    vlan_id = fields.Integer(
        string='VLAN ID', 
        help="VLAN ID for the network (1-4094)."
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

    purpose = fields.Selection([
        ('corporate', 'Corporate'),
        ('guest', 'Guest'),
        ('wan', 'WAN'),
        ('vlan-only', 'VLAN Only'),
        ('remote-user-vpn', 'Remote User VPN'),
        ('site-vpn', 'Site VPN'),
        ('vlan', 'VLAN'),
        ('wan2', 'WAN2'),
        ('sip', 'SIP'),
        ('unifionly', 'UniFi Only')
    ], string='Purpose', default='corporate')

    network_group = fields.Selection([
        ('LAN', 'LAN'),
        ('WAN', 'WAN'),
        ('CORP', 'Corporate'),
        ('GUEST', 'Guest'),
        ('VPN', 'VPN'),
        ('VLAN', 'VLAN')
    ], string='Network Group', default='LAN')

    firewall_enabled = fields.Boolean(
        string='Enable Firewall',
        default=True,
        help="Enable or disable firewall for this network"
    )

    firewall_type = fields.Selection([
        ('auto', 'Auto'),
        ('custom', 'Custom')
    ], string='Firewall Type', default='auto')

    firewall_default_action = fields.Selection([
        ('accept', 'Accept'),
        ('drop', 'Drop'),
        ('reject', 'Reject')
    ], string='Default Action', default='drop')

    inter_client_routing = fields.Boolean(
        string='Inter-Client Routing',
        default=True,
        help="Allow clients on this network to communicate with each other"
    )

    dhcp_enabled = fields.Boolean(
        string='DHCP Enabled',
        default=True
    )

    dhcp_start = fields.Char(
        string='DHCP Start',
        help="Start of DHCP range"
    )

    dhcp_stop = fields.Char(
        string='DHCP Stop',
        help="End of DHCP range"
    )

    domain_name = fields.Char(
        string='Domain Name'
    )

    site_id = fields.Char(
        string='Site ID',
        readonly=True
    )

    subnet = fields.Char(
        string='Subnet',
        help="Network subnet in CIDR notation"
    )

    @api.constrains('cidr')
    def _check_cidr_format(self):
        for record in self:
            if record.cidr:
                # Validate CIDR format (e.g., 192.168.1.0/24)
                cidr_pattern = r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$'
                if not re.match(cidr_pattern, record.cidr):
                    raise ValidationError('Invalid CIDR format. Example of valid format: 192.168.1.0/24')
                
                # Validate IP address parts
                ip = record.cidr.split('/')[0]
                parts = ip.split('.')
                for part in parts:
                    if not 0 <= int(part) <= 255:
                        raise ValidationError('IP address parts must be between 0 and 255')
                
                # Validate subnet mask
                mask = int(record.cidr.split('/')[1])
                if not 0 <= mask <= 32:
                    raise ValidationError('Subnet mask must be between 0 and 32')

    @api.constrains('gateway')
    def _check_gateway_format(self):
        for record in self:
            if record.gateway:
                # Validate IP format
                ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
                if not re.match(ip_pattern, record.gateway):
                    raise ValidationError('Invalid Gateway IP format. Example of valid format: 192.168.1.1')
                
                # Validate IP parts
                parts = record.gateway.split('.')
                for part in parts:
                    if not 0 <= int(part) <= 255:
                        raise ValidationError('Gateway IP parts must be between 0 and 255')

    @api.constrains('vlan_id')
    def _check_vlan_id(self):
        for record in self:
            if record.vlan_id and not (1 <= record.vlan_id <= 4094):
                raise ValidationError('VLAN ID must be between 1 and 4094')

    @api.model
    def sync_from_controller(self, client, controller_id):
        """Synchronize networks from UniFi Controller."""
        networks = client.get_networks()
        
        for network in networks:
            # Extract network details
            values = {
                'name': network.get('name', ''),
                'unifi_id': network.get('_id', ''),
                'description': network.get('purpose', ''),
                'last_sync': fields.Datetime.now(),
                'ctrl_id': controller_id,
                'purpose': network.get('purpose', 'corporate'),
                'network_group': network.get('networkgroup', 'LAN'),
                'dhcp_enabled': network.get('dhcp_enabled', True),
                'dhcp_start': network.get('dhcp_start', ''),
                'dhcp_stop': network.get('dhcp_stop', ''),
                'domain_name': network.get('domain_name', ''),
                'site_id': network.get('site_id', ''),
                'subnet': network.get('subnet', ''),
                'gateway': network.get('gateway_ip', ''),
                'vlan_id': network.get('vlan', 0),
            }

            # Handle CIDR for different network types
            if network.get('purpose') == 'wan':
                values['cidr'] = '0.0.0.0/0'  # Default CIDR for WAN
            else:
                values['cidr'] = network.get('ip_subnet', '0.0.0.0/0')
            
            # Update existing or create new
            existing = self.search([('unifi_id', '=', values['unifi_id'])])
            if existing:
                existing.write(values)
            else:
                self.create(values)

    def sync_to_unifi(self):
        """Push network changes to UniFi Controller"""
        self.ensure_one()
        client = self.env['unifi.client'].get_client()
        
        network_data = {
            'name': self.name,
            'subnet': self.cidr,
            'gateway_ip': self.gateway,
            'vlan': self.vlan_id,
            'purpose': self.description,
            'purpose': self.purpose,
            'network_group': self.network_group,
            'dhcp_enabled': self.dhcp_enabled,
            'dhcp_start': self.dhcp_start,
            'dhcp_stop': self.dhcp_stop,
            'domain_name': self.domain_name,
        }
        
        if self.unifi_id:
            # Update existing network
            client.update_network(self.unifi_id, network_data)
        else:
            # Create new network
            result = client.create_network(network_data)
            if result and result.get('_id'):
                self.write({
                    'unifi_id': result['_id'],
                    'last_sync': fields.Datetime.now()
                })
