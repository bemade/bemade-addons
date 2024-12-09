from odoo import models, fields

class Wifi(models.Model):
    _name = 'unifi.wifi'
    _description = 'Unifi WiFi Network'

    name = fields.Char(string='WiFi Name (SSID)', required=True)
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
        string='VLAN', 
        help="VLAN associated with this WiFi network."
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
