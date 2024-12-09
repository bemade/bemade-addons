from odoo import models, fields

class Network(models.Model):
    _name = 'unifi.network'
    _description = 'Unifi Network'

    name = fields.Char(
        string='Network Name',
        required=True
        )

    cidr = fields.Char(
        string='CIDR', 
        required=True, 
        help="CIDR notation for the network (e.g., 192.168.1.0/24)."
        )

    gateway = fields.Char(
        string='Gateway', 
        help="Gateway IP address for the network."
        )

    vlan_id = fields.Integer(
        string='VLAN ID', 
        help="VLAN ID for the network."
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
