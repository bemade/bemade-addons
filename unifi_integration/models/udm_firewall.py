# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UdmFirewallRule(models.Model):
    """Représentation d'une règle de pare-feu dans l'UDM Pro"""
    _name = 'udm.firewall.rule'
    _description = 'UDM Pro Firewall Rule'
    
    config_id = fields.Many2one('udm.configuration', string='Configuration', ondelete='cascade')
    name = fields.Char(string='Name', required=True)
    enabled = fields.Boolean(string='Enabled', default=True)
    action = fields.Selection([
        ('accept', 'Accept'),
        ('drop', 'Drop'),
        ('reject', 'Reject')
    ], string='Action')
    protocol = fields.Selection([
        ('tcp', 'TCP'),
        ('udp', 'UDP'),
        ('icmp', 'ICMP'),
        ('all', 'All')
    ], string='Protocol')
    src_address = fields.Char(string='Source Address')
    dst_address = fields.Char(string='Destination Address')
    src_port = fields.Char(string='Source Port')
    dst_port = fields.Char(string='Destination Port')
    raw_data = fields.Text(string='Raw Data')
    
    # Champs calculés
    rule_summary = fields.Char(string='Rule Summary', compute='_compute_rule_summary')
    
    @api.depends('action', 'protocol', 'src_address', 'dst_address', 'src_port', 'dst_port')
    def _compute_rule_summary(self):
        for record in self:
            parts = []
            
            if record.action:
                parts.append(record.action.upper())
            
            if record.protocol:
                parts.append(record.protocol.upper())
            
            if record.src_address:
                src = f"from {record.src_address}"
                if record.src_port:
                    src += f":{record.src_port}"
                parts.append(src)
            
            if record.dst_address:
                dst = f"to {record.dst_address}"
                if record.dst_port:
                    dst += f":{record.dst_port}"
                parts.append(dst)
            
            record.rule_summary = ' '.join(parts) if parts else 'No details'
