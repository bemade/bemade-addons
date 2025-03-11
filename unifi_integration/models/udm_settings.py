# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UdmSettings(models.Model):
    """General configuration of the UDM Pro"""
    _name = 'udm.settings'
    _description = 'UDM Pro Settings'
    
    # Basic fields
    site_id = fields.Many2one('udm.site', string='Site', required=True, ondelete='cascade',
                             help='Site these settings belong to')
    name = fields.Char(string='Name', compute='_compute_name', store=True,
                      help='Settings name for display')
    
    # Time settings
    timezone = fields.Selection([
        ('UTC', 'UTC'),
        ('America/Montreal', 'America/Montreal'),
        ('America/New_York', 'America/New_York'),
        ('America/Toronto', 'America/Toronto'),
        ('Europe/Paris', 'Europe/Paris')
    ], string='Timezone', default='America/Montreal',
        help='Timezone for this site')
    ntp_enabled = fields.Boolean(string='NTP Enabled', default=True,
                                help='Enable NTP synchronization')
    ntp_servers = fields.Char(string='NTP Servers',
                             help='Comma-separated list of NTP servers')
    
    # DNS settings
    dns_enabled = fields.Boolean(string='DNS Enabled', default=True,
                                help='Enable DNS service')
    dns_servers = fields.Char(string='DNS Servers',
                             help='Comma-separated list of DNS servers')
    dns_forwarding = fields.Boolean(string='DNS Forwarding', default=True,
                                   help='Enable DNS forwarding')
    
    # Advanced settings
    upnp_enabled = fields.Boolean(string='UPnP Enabled', default=False,
                                 help='Enable Universal Plug and Play')
    mdns_enabled = fields.Boolean(string='mDNS Enabled', default=True,
                                 help='Enable multicast DNS')
    igmp_proxy = fields.Boolean(string='IGMP Proxy', default=False,
                               help='Enable IGMP proxy')
    
    # Raw data
    raw_data = fields.Text(string='Raw Data',
                          help='Raw settings data in JSON format')
    
    # Computed fields
    ntp_server_list = fields.Many2many('ir.model.data', string='NTP Server List',
                                     compute='_compute_server_lists',
                                     help='List of NTP servers for display')
    dns_server_list = fields.Many2many('ir.model.data', string='DNS Server List',
                                     compute='_compute_server_lists',
                                     help='List of DNS servers for display')
    
    @api.depends('site_id')
    def _compute_name(self):
        """Compute a display name for the settings
        
        The name is based on the site name and includes a timestamp to
        differentiate between multiple settings records for the same site.
        """
        for record in self:
            if record.site_id:
                record.name = f'{record.site_id.name} Settings'
            else:
                record.name = 'New Settings'
    
    @api.depends('ntp_servers', 'dns_servers')
    def _compute_server_lists(self):
        """Convert comma-separated server lists to Many2many fields
        
        This method splits the NTP and DNS server strings into lists
        for display in the user interface. The lists are stored in
        technical fields that are not persisted to the database.
        """
        for record in self:
            # Convert NTP servers string to list
            if record.ntp_servers:
                ntp_servers = [s.strip() for s in record.ntp_servers.split(',')]
                record.ntp_server_list = [(6, 0, ntp_servers)]
            else:
                record.ntp_server_list = False
            
            # Convert DNS servers string to list
            if record.dns_servers:
                dns_servers = [s.strip() for s in record.dns_servers.split(',')]
                record.dns_server_list = [(6, 0, dns_servers)]
            else:
                record.dns_server_list = False
