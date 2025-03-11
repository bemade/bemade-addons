# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UdmRoutingConfig(models.Model):
    """Routing configuration for the UDM Pro"""
    _name = 'udm.routing.config'
    _description = 'UDM Pro Routing Configuration'
    
    # Site this routing configuration belongs to
    site_id = fields.Many2one('udm.site', string='Site', required=True, ondelete='cascade')
    
    # Routing settings
    ospf_enabled = fields.Boolean(string='OSPF Enabled', default=False,
                                help='Enable OSPF routing protocol')
    static_routes = fields.Text(string='Static Routes',
                              help='List of static routes in format: network/prefix via nexthop')
    raw_data = fields.Text(string='Raw Data',
                          help='Raw configuration data in JSON format')
