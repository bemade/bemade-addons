# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UdmFirewallRule(models.Model):
    """Represents a firewall rule in the UniFi system
    
    This model stores firewall rules that control network traffic. Each rule
    specifies what traffic is allowed or blocked based on various criteria such
    as source/destination addresses, ports, and protocols.
    
    Rules are linked to a specific site and are automatically deleted when
    the site is deleted (cascade).
    """
    _name = 'udm.firewall.rule'
    _description = 'UniFi Firewall Rule'
    _order = 'sequence, id'
    
    site_id = fields.Many2one('udm.site', string='Site', required=True,
                             ondelete='cascade',
                             help='Site this firewall rule belongs to')
    name = fields.Char(string='Name', required=True,
                      help='Rule name')
    description = fields.Text(string='Description',
                            help='Detailed description of the rule purpose')
    enabled = fields.Boolean(string='Enabled', default=True,
                           help='Whether this rule is active')
    sequence = fields.Integer(string='Sequence', default=10,
                            help='Order in which rules are evaluated')
    action = fields.Selection([
        ('accept', 'Accept'),
        ('drop', 'Drop'),
        ('reject', 'Reject')
    ], string='Action', required=True, default='drop',
        help='Action to take when rule matches')
    protocol = fields.Selection([
        ('tcp', 'TCP'),
        ('udp', 'UDP'),
        ('icmp', 'ICMP'),
        ('all', 'All')
    ], string='Protocol', required=True, default='all',
        help='Network protocol this rule applies to')
    source = fields.Char(string='Source',
                        help='Source network or IP address in CIDR format')
    destination = fields.Char(string='Destination',
                            help='Destination network or IP address in CIDR format')
    src_address = fields.Char(string='Source Address',
                            help='Legacy field, use source instead')
    dst_address = fields.Char(string='Destination Address',
                            help='Legacy field, use destination instead')
    src_port = fields.Char(string='Source Port',
                          help='Source port number or range (e.g. 80 or 1024-2048)')
    dst_port = fields.Char(string='Destination Port',
                          help='Destination port number or range (e.g. 80 or 1024-2048)')
    raw_data = fields.Text(string='Raw Data',
                          help='Raw firewall rule data in JSON format')
    
    # Computed fields
    rule_summary = fields.Char(string='Rule Summary', compute='_compute_rule_summary')
    
    @api.depends('action', 'protocol', 'src_address', 'dst_address', 'src_port', 'dst_port')
    def _compute_rule_summary(self):
        """Compute a human-readable summary of the firewall rule
        
        This method generates a concise description of the rule's action,
        protocol, and source/destination addresses and ports. The summary
        is used in list views and reports to quickly understand what the
        rule does without viewing all details.
        
        Example summaries:
        - ACCEPT TCP from 192.168.1.0/24:80 to 10.0.0.0/8:443
        - DROP ICMP from 172.16.0.0/16 to any
        - REJECT UDP from any to 192.168.2.10:53
        """
        for record in self:
            parts = []
            
            if record.action:
                parts.append(record.action.upper())
            
            if record.protocol:
                parts.append(record.protocol.upper())
            
            # Use new source/destination fields if available, fall back to legacy fields
            src_addr = record.source or record.src_address or 'any'
            dst_addr = record.destination or record.dst_address or 'any'
            
            src = f"from {src_addr}"
            if record.src_port:
                src += f":{record.src_port}"
            parts.append(src)
            
            dst = f"to {dst_addr}"
            if record.dst_port:
                dst += f":{record.dst_port}"
            parts.append(dst)
            
            record.rule_summary = ' '.join(parts)
