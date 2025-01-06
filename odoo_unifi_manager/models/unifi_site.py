from odoo import models, fields, api

class UnifiSite(models.Model):
    _name = 'unifi.site'
    _description = 'UniFi Site'

    name = fields.Char(string='Name', required=True)
    site_id = fields.Char(string='Site ID', required=True)
    description = fields.Text(string='Description')
    controller_id = fields.Many2one('unifi.ctrl', string='Controller', required=True)
    device_ids = fields.One2many('unifi.device', 'site_id', string='Devices')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('site_id_controller_uniq', 'unique(site_id,controller_id)', 'Site ID must be unique per controller!')
    ]
