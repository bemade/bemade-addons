# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UdmRoutingConfig(models.Model):
    """Routing configuration for the UniFi system
    
    This model stores routing configuration for both UDM/UDR controllers.
    It manages routing settings such as OSPF and static routes.
    
    Routing configuration is linked to a specific site and is automatically deleted
    when the site is deleted (cascade).
    """
    _name = 'udm.routing.config'
    _description = 'UniFi Routing Configuration'
    
    site_id = fields.Many2one('udm.site', string='Site', required=True,
                             ondelete='cascade',
                             help='Site this routing configuration belongs to')
    ospf_enabled = fields.Boolean(string='OSPF Enabled', default=False,
                                help='Enable OSPF routing')
    static_routes = fields.Text(string='Static Routes',
                              help='Comma-separated list of static routes in format: network/prefix via nexthop')
    raw_data = fields.Text(string='Raw Data',
                          help='Raw routing configuration data in JSON format')
