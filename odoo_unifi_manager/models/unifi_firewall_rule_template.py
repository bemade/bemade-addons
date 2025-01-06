from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re
import ipaddress

class FirewallRuleTemplate(models.Model):
    _name = 'unifi.firewall.rule.template'
    _description = 'Firewall Rule Template'
    _order = 'rule_index'

    name = fields.Char(
        string='Template Name', 
        required=True
    )

    ctrl_id = fields.Many2one(
        'unifi.ctrl', 
        string='Controller', 
        required=True, 
        help="Controller where this rule is applied."
    )

    enabled = fields.Boolean(
        string='Enabled',
        default=True,
        help="Whether this rule is active"
    )

    ruleset = fields.Selection([
        ('LAN_IN', 'LAN In'),
        ('LAN_OUT', 'LAN Out'),
        ('LAN_LOCAL', 'LAN Local'),
        ('WAN_IN', 'WAN In'),
        ('WAN_OUT', 'WAN Out'),
        ('WAN_LOCAL', 'WAN Local')
    ], string='Rule Set', required=True, default='LAN_IN')

    rule_index = fields.Integer(
        string='Rule Index',
        help="Order in which the rule is applied",
        default=2000
    )

    action = fields.Selection(
        selection=[
            ('accept', 'Accept'), 
            ('drop', 'Drop'),
            ('reject', 'Reject')
        ], 
        string='Action', 
        required=True
    )

    src_ip = fields.Char(
        string='Source IP', 
        help="Source IP address or network (e.g., 192.168.1.0/24)"
    )

    dst_ip = fields.Char(
        string='Destination IP', 
        help="Destination IP address or network (e.g., 192.168.1.0/24)"
    )

    protocol = fields.Selection(
        selection=[
            ('all', 'All'),
            ('tcp', 'TCP'), 
            ('udp', 'UDP'),
            ('icmp', 'ICMP')
        ], 
        string='Protocol', 
        required=True,
        default='all'
    )

    port = fields.Char(
        string='Port', 
        help="Port or port range (e.g., 80 or 8000-9000)"
    )

    firewall_group_id = fields.Many2one(
        'unifi.firewall.group',
        string='Firewall Group',
        help="Associated firewall group"
    )

    categories = fields.Many2many(
        'unifi.dpi.category',
        string='DPI Categories',
        help="Deep Packet Inspection categories this rule applies to"
    )

    @api.constrains('port')
    def _check_port(self):
        """Validate port format."""
        for record in self:
            if not record.port:
                continue
            
            # Check single port
            if record.port.isdigit():
                port = int(record.port)
                if not (1 <= port <= 65535):
                    raise ValidationError("Port must be between 1 and 65535")
                continue
            
            # Check port range
            if '-' in record.port:
                try:
                    start, end = map(int, record.port.split('-'))
                    if not (1 <= start <= end <= 65535):
                        raise ValidationError("Port range must be between 1 and 65535")
                except ValueError:
                    raise ValidationError("Invalid port range format. Use format: start-end")
            else:
                raise ValidationError("Invalid port format. Use a single port or range (e.g., 80 or 8000-9000)")

    @api.constrains('src_ip', 'dst_ip')
    def _check_ip_addresses(self):
        """Validate IP address formats."""
        for record in self:
            for field in [record.src_ip, record.dst_ip]:
                if not field:
                    continue
                try:
                    # Handle CIDR notation
                    if '/' in field:
                        ipaddress.ip_network(field)
                    else:
                        ipaddress.ip_address(field)
                except ValueError:
                    raise ValidationError(f"Invalid IP address format: {field}")

    def copy_to_controller(self):
        """Copy this template to the actual firewall rules on the controller."""
        self.ensure_one()
        client = self.ctrl_id.get_client()
        
        rule_data = {
            'name': self.name,
            'enabled': self.enabled,
            'ruleset': self.ruleset,
            'rule_index': self.rule_index,
            'protocol': self.protocol,
            'action': self.action,
        }

        if self.port:
            rule_data['port'] = self.port
        if self.src_ip:
            rule_data['src'] = self.src_ip
        if self.dst_ip:
            rule_data['dst'] = self.dst_ip
        if self.categories:
            rule_data['categories'] = self.categories.mapped('category_id')
        
        return client.create_firewall_rule(rule_data)
