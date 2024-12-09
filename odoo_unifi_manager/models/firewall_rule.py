from odoo import models, fields, api

class FirewallRule(models.Model):
    _name = 'unifi.firewall.rule'
    _description = 'Unifi Firewall Rule'

    name = fields.Char(
        string='Rule Name', 
        required=True
        )

    ctrl_id = fields.Many2one(
        'unifi.ctrl', 
        string='Controller', 
        required=True, 
        help="Controller where this rule is applied."
    )

    action = fields.Selection(
        selection=[
            ('accept', 'Accept'), 
            ('drop', 'Drop')
        ],
        string='Action', 
        required=True
        )

    src_ip = fields.Char(
        string='Source IP', 
        help="Source IP address (can be left empty)"
        )

    dst_ip = fields.Char(
        string='Destination IP', 
        help="Destination IP address (can be left empty)"
        )

    protocol = fields.Selection(
        selection=[
            ('tcp', 'TCP'), 
            ('udp', 'UDP')
        ], 
        string='Protocol', 
        required=True
        )

    port = fields.Char(
        string='Port', 
        help="Port or port range (e.g., 80 or 8000-9000)"
        )
