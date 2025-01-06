from odoo import models, fields, api
from odoo.exceptions import ValidationError

class FirewallRuleWizard(models.TransientModel):
    _name = 'unifi.firewall.rule.wizard'
    _description = 'Wizard to Create Firewall Rule from Template'

    template_id = fields.Many2one(
        'unifi.firewall.rule.template', 
        string='Template', 
        required=True,
        help="Select the template to create a firewall rule."
    )

    name = fields.Char(
        string='Name of the new firewall rule', 
        required=True
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

    def create_firewall_rule(self):
        self.ensure_one()
        template = self.template_id
        self.env['unifi.firewall.rule'].create({
            'name': self.name,
            'action': self.action,
            'src_ip': self.src_ip,
            'dst_ip': self.dst_ip,
            'protocol': self.protocol,
            'port': self.port,
        })

    @api.constrains('port')
    def _check_port(self):
        if self.port:
            if not self.port.isdigit() and '-' not in self.port:
                raise ValidationError("Port must be a number or a valid range (e.g., 80 or 8000-9000).")