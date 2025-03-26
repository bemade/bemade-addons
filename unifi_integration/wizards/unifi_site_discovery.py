# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UnifiSiteDiscovery(models.TransientModel):
    """Transient model to store discovered UniFi sites"""
    _name = 'unifi.site.discovery'
    _description = 'UniFi Site Discovery'

    name = fields.Char(string='Site Name', required=True)
    site_id = fields.Char(string='Site ID', required=True)
    api_type = fields.Selection([
        ('controller', 'UniFi Controller (Local)'),
        ('site_manager', 'UniFi Site Manager (Cloud)')
    ], string='API Type', required=True)
    details = fields.Text(string='Site Details', help="JSON representation of the site details")
    
    def name_get(self):
        """Override name_get to display site name and ID"""
        result = []
        for record in self:
            name = f"{record.name} ({record.site_id})"
            result.append((record.id, name))
        return result
