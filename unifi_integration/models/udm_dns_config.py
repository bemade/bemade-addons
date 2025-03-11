# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UdmDnsConfig(models.Model):
    """DNS configuration for the UDM Pro"""
    _name = 'udm.dns.config'
    _description = 'UDM Pro DNS Configuration'
    
    # Site this DNS configuration belongs to
    site_id = fields.Many2one('udm.site', string='Site', required=True, ondelete='cascade')
    
    # DNS settings
    enabled = fields.Boolean(string='Enabled', default=True,
                           help='Whether DNS service is enabled')
    filters_enabled = fields.Boolean(string='Content Filtering Enabled', default=False,
                                   help='Enable content filtering on DNS queries')
    custom_dns = fields.Char(string='Custom DNS Servers',
                           help='Comma-separated list of custom DNS servers')
    raw_data = fields.Text(string='Raw Data',
                          help='Raw configuration data in JSON format')
