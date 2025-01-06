"""UniFi Device Model."""
from odoo import models, fields, api

class UnifiDevice(models.Model):
    _name = 'unifi.device'
    _description = 'UniFi Network Device'

    name = fields.Char(
        string='Name',
        required=True,
        help="Device name"
    )

    mac = fields.Char(
        string='MAC Address',
        required=True,
        help="Device MAC address"
    )

    model = fields.Char(
        string='Model',
        help="Device model"
    )

    type = fields.Selection([
        ('uap', 'Access Point'),
        ('ugw', 'Gateway'),
        ('usw', 'Switch'),
        ('udm', 'Dream Machine'),
        ('other', 'Other')
    ], string='Type', required=True)

    ip_address = fields.Char(
        string='IP Address',
        help="Device IP address"
    )

    version = fields.Char(
        string='Firmware Version',
        help="Device firmware version"
    )

    status = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('unknown', 'Unknown')
    ], string='Status', default='unknown')

    last_seen = fields.Datetime(
        string='Last Seen',
        help="Last time the device was seen online"
    )

    controller_id = fields.Many2one(
        'unifi.ctrl',
        string='Controller',
        required=True,
        ondelete='cascade'
    )

    site_id = fields.Char(
        string='Site ID',
        help="UniFi site identifier"
    )

    _sql_constraints = [
        ('unique_mac_per_controller', 'unique(mac,controller_id)', 
         'A device with this MAC address already exists for this controller!')
    ]
