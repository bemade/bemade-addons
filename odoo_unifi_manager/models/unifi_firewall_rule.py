from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re
from datetime import datetime

class FirewallRule(models.Model):
    _name = 'unifi.firewall.rule'
    _description = 'Unifi Firewall Rule'
    _order = 'sequence'

    name = fields.Char(
        string='Rule Name', 
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

    sequence = fields.Integer(
        string='Sequence',
        default=2000,
        help="Rules are processed in sequence order"
    )

    enabled = fields.Boolean(
        string='Enabled',
        default=True,
        help="Enable or disable this rule"
    )

    description = fields.Text(
        string='Description',
        help="Detailed description of the rule's purpose"
    )

    controller_id = fields.Many2one(
        'unifi.ctrl', 
        string='Controller', 
        required=True, 
        help="Controller where this rule is applied"
    )

    direction = fields.Selection([
        ('in', 'Inbound'),
        ('out', 'Outbound'),
        ('local', 'Local'),
        ('both', 'Both Directions')
    ], string='Direction', required=True, default='in')

    action = fields.Selection([
        ('accept', 'Accept'), 
        ('drop', 'Drop'),
        ('reject', 'Reject')
    ], string='Action', required=True, default='drop')

    ruleset = fields.Selection([
        ('LAN_IN', 'LAN Inbound'),
        ('LAN_OUT', 'LAN Outbound'),
        ('LAN_LOCAL', 'LAN Local'),
        ('WAN_IN', 'WAN Inbound'),
        ('WAN_OUT', 'WAN Outbound'),
        ('WAN_LOCAL', 'WAN Local'),
        ('GUEST_IN', 'Guest Inbound'),
        ('GUEST_OUT', 'Guest Outbound'),
        ('GUEST_LOCAL', 'Guest Local')
    ], string='Rule Set', required=True, default='LAN_IN')

    rule_index = fields.Integer(
        string='Rule Index',
        default=2000,
        help="Position of the rule within its ruleset"
    )

    src_network_id = fields.Many2one(
        'unifi.network',
        string='Source Network',
        help="Source network for this rule"
    )

    src_address = fields.Char(
        string='Source Address', 
        help="Source IP address or CIDR (e.g., 192.168.1.0/24)"
    )

    dst_network_id = fields.Many2one(
        'unifi.network',
        string='Destination Network',
        help="Destination network for this rule"
    )

    dst_address = fields.Char(
        string='Destination Address', 
        help="Destination IP address or CIDR (e.g., 192.168.1.0/24)"
    )

    protocol = fields.Selection([
        ('all', 'All'),
        ('tcp', 'TCP'), 
        ('udp', 'UDP'),
        ('icmp', 'ICMP')
    ], string='Protocol', required=True, default='all')

    src_port = fields.Char(
        string='Source Port', 
        help="Source port or port range (e.g., 80 or 8000-9000)"
    )

    dst_port = fields.Char(
        string='Destination Port', 
        help="Destination port or port range (e.g., 80 or 8000-9000)"
    )

    icmp_type = fields.Selection([
        ('0', 'Echo Reply'),
        ('3', 'Destination Unreachable'),
        ('8', 'Echo Request'),
        ('11', 'Time Exceeded')
    ], string='ICMP Type')

    state_new = fields.Boolean(string='New Connections', default=True)
    state_established = fields.Boolean(string='Established Connections', default=True)
    state_invalid = fields.Boolean(string='Invalid Connections', default=False)
    state_related = fields.Boolean(string='Related Connections', default=True)

    @api.constrains('src_address', 'dst_address')
    def _check_ip_format(self):
        for record in self:
            for field, value in [('src_address', record.src_address), ('dst_address', record.dst_address)]:
                if value:
                    # Check if it's a CIDR notation
                    if '/' in value:
                        try:
                            ip, mask = value.split('/')
                            if not (0 <= int(mask) <= 32):
                                raise ValidationError(f'Invalid CIDR mask in {field}. Must be between 0 and 32.')
                        except ValueError:
                            raise ValidationError(f'Invalid CIDR format in {field}. Use format like 192.168.1.0/24')
                        ip_to_check = ip
                    else:
                        ip_to_check = value

                    # Validate IP format
                    parts = ip_to_check.split('.')
                    if len(parts) != 4:
                        raise ValidationError(f'Invalid IP format in {field}. Must be like 192.168.1.0')
                    for part in parts:
                        try:
                            if not (0 <= int(part) <= 255):
                                raise ValidationError(f'IP parts must be between 0 and 255 in {field}')
                        except ValueError:
                            raise ValidationError(f'Invalid IP format in {field}')

    @api.constrains('src_port', 'dst_port')
    def _check_port_format(self):
        for record in self:
            for field, value in [('src_port', record.src_port), ('dst_port', record.dst_port)]:
                if value:
                    # Check if it's a port range
                    if '-' in value:
                        try:
                            start, end = map(int, value.split('-'))
                            if not (0 <= start <= 65535 and 0 <= end <= 65535 and start <= end):
                                raise ValidationError(f'Invalid port range in {field}. Must be between 0-65535 and start must be <= end')
                        except ValueError:
                            raise ValidationError(f'Invalid port range format in {field}. Use format like 8000-9000')
                    else:
                        try:
                            port = int(value)
                            if not (0 <= port <= 65535):
                                raise ValidationError(f'Port must be between 0 and 65535 in {field}')
                        except ValueError:
                            raise ValidationError(f'Invalid port number in {field}')

    @api.model
    def sync_from_controller(self, client, controller_id):
        """Synchronize firewall rules from UniFi Controller."""
        rules = client.get_firewall_rules()
        
        for rule in rules:
            values = {
                'name': rule.get('name', 'Unnamed Rule'),
                'unifi_id': rule.get('_id'),
                'enabled': rule.get('enabled', True),
                'action': rule.get('action', 'drop'),
                'protocol': rule.get('protocol', 'all'),
                'src_address': rule.get('src_address') or rule.get('src_ip', ''),
                'dst_address': rule.get('dst_address') or rule.get('dst_ip', ''),
                'src_port': rule.get('src_port', ''),
                'dst_port': rule.get('dst_port', ''),
                'direction': rule.get('direction', 'in'),
                'ruleset': rule.get('ruleset', 'LAN_IN'),
                'rule_index': rule.get('rule_index', 2000),
                'description': rule.get('description', ''),
                'last_sync': fields.Datetime.now(),
                'controller_id': controller_id,
            }
            
            # Update existing or create new
            existing = self.search([
                ('unifi_id', '=', values['unifi_id']),
                ('controller_id', '=', controller_id)
            ])
            if existing:
                existing.write(values)
            else:
                self.create(values)

    def sync_to_controller(self):
        """Synchronize firewall rule to UniFi Controller."""
        self.ensure_one()
        client = self.controller_id.get_client()
        
        rule_data = {
            'name': self.name,
            'enabled': self.enabled,
            'action': self.action,
            'protocol': self.protocol,
            'src_address': self.src_address,
            'dst_address': self.dst_address,
            'src_port': self.src_port,
            'dst_port': self.dst_port,
            'direction': self.direction,
            'ruleset': self.ruleset,
            'rule_index': self.rule_index,
            'description': self.description,
        }
        
        if self.unifi_id:
            # Update existing rule
            client.update_firewall_rule(self.unifi_id, rule_data)
        else:
            # Create new rule
            result = client.create_firewall_rule(rule_data)
            if result and result.get('_id'):
                self.write({
                    'unifi_id': result['_id'],
                    'last_sync': fields.Datetime.now()
                })
