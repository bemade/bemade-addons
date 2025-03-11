# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UdmPortForward(models.Model):
    """Represents a port forwarding rule in the UniFi system
    
    This model stores port forwarding rules that allow external access to
    internal services. Each rule maps an external port to an internal
    IP address and port.
    
    Port forwards are linked to a specific site and are automatically deleted
    when the site is deleted (cascade).
    """
    _name = 'udm.port.forward'
    _description = 'UniFi Port Forward'
    _order = 'sequence, id'
    
    site_id = fields.Many2one('udm.site', string='Site', required=True,
                             ondelete='cascade',
                             help='Site this port forward belongs to')
    name = fields.Char(string='Name', required=True,
                      help='Rule name')
    description = fields.Text(string='Description',
                            help='Detailed description of the port forward purpose')
    enabled = fields.Boolean(string='Enabled', default=True,
                           help='Whether this rule is active')
    sequence = fields.Integer(string='Sequence', default=10,
                            help='Order in which rules are evaluated')
    protocol = fields.Selection([
        ('tcp', 'TCP'),
        ('udp', 'UDP'),
        ('tcp_udp', 'TCP & UDP')
    ], string='Protocol', required=True, default='tcp',
        help='Network protocol to forward')
    source = fields.Char(string='Source',
                        help='Source network or IP address in CIDR format')
    dst_port = fields.Char(string='Destination Port', required=True,
                          help='External port number or range (e.g. 80 or 1024-2048)')
    fwd_ip = fields.Char(string='Forward IP', required=True,
                        help='Internal IP address to forward to')
    fwd_port = fields.Char(string='Forward Port', required=True,
                          help='Internal port number or range')
    raw_data = fields.Text(string='Raw Data',
                          help='Raw port forward data in JSON format')
    
    # Computed fields
    rule_summary = fields.Char(string='Rule Summary', compute='_compute_rule_summary')
    
    @api.depends('protocol', 'source', 'dst_port', 'fwd_ip', 'fwd_port')
    def _compute_rule_summary(self):
        """Compute a human-readable summary of the port forward rule
        
        This method generates a concise description of the rule's protocol,
        source, and port mappings. The summary is used in list views and
        reports to quickly understand what the rule does without viewing
        all details.
        
        Example summaries:
        - TCP from any:80 to 192.168.1.100:8080
        - UDP from 203.0.113.0/24:53 to 192.168.2.10:53
        - TCP & UDP from any:25565 to 192.168.3.50:25565
        """
        for record in self:
            parts = []
            
            if record.protocol:
                parts.append(record.protocol.upper())
            
            src = f"from {record.source or 'any'}"
            if record.dst_port:
                src += f":{record.dst_port}"
            parts.append(src)
            
            dst = f"to {record.fwd_ip}"
            if record.fwd_port:
                dst += f":{record.fwd_port}"
            parts.append(dst)
            
            record.rule_summary = ' '.join(parts)
