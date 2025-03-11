# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import timedelta

class UdmUser(models.Model):
    """Represents a user in the UniFi system
    
    This model stores information about users who have access to the UniFi
    network, including their roles and permissions. Users can be administrators,
    operators, or read-only viewers.
    
    Users are linked to a specific site and are automatically deleted when
    the site is deleted (cascade).
    """
    _name = 'udm.user'
    _description = 'UniFi User'
    
    # Basic fields
    site_id = fields.Many2one('udm.site', string='Site', required=True,
                             ondelete='cascade',
                             help='Site this user belongs to')
    name = fields.Char(string='Name', required=True,
                      help='User full name')
    email = fields.Char(string='Email',
                       help='User email address')
    mac_address = fields.Char(string='MAC Address',
                            help='Device MAC address')
    ip_address = fields.Char(string='IP Address',
                           help='Current IP address')
    network_id = fields.Many2one('udm.network', string='Network',
                               ondelete='set null',
                               help='Network this user is connected to')
    
    # Role and permissions
    role = fields.Selection([
        ('admin', 'Administrator'),
        ('operator', 'Operator'),
        ('viewer', 'Viewer')
    ], string='Role', required=True, default='viewer',
        help='User role and permissions level')
    enabled = fields.Boolean(string='Enabled', default=True,
                           help='Whether the user account is active')
    
    # Connection status
    status = fields.Selection([
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('idle', 'Idle')
    ], string='Status', default='disconnected',
        help='Current connection status of the user')
    last_seen = fields.Datetime(string='Last Seen',
                               help='Last time the user was seen online')
    
    # Technical fields
    raw_data = fields.Text(string='Raw Data',
                          help='Raw user data in JSON format')
    
    # Computed fields
    is_admin = fields.Boolean(string='Is Admin', compute='_compute_is_admin', store=True,
                            help='Whether this user has administrator privileges')
    is_connected = fields.Boolean(string='Is Connected', compute='_compute_is_connected',
                                 store=True, help='Whether this user is currently connected')
    
    @api.depends('role')
    def _compute_is_admin(self):
        """Compute whether the user has administrator privileges
        
        This is a convenience field that makes it easy to filter for or check
        if a user has admin rights without parsing the role field.
        """
        for record in self:
            record.is_admin = record.role == 'admin'
    
    @api.depends('status')
    def _compute_is_connected(self):
        """Compute whether the user is currently connected
        
        This is a convenience field that makes it easy to filter for or check
        if a user is currently connected without parsing the status field.
        """
        for record in self:
            record.is_connected = record.status == 'connected'
    
    def _update_status(self):
        """Update the user's connection status based on last seen time
        
        This method is called periodically to update the user's status:
        - If last seen within 5 minutes: Connected
        - If last seen within 30 minutes: Idle
        - Otherwise: Disconnected
        """
        now = fields.Datetime.now()
        for record in self:
            if not record.last_seen:
                record.status = 'disconnected'
                continue
                
            delta = now - record.last_seen
            if delta <= timedelta(minutes=5):
                record.status = 'connected'
            elif delta <= timedelta(minutes=30):
                record.status = 'idle'
            else:
                record.status = 'disconnected'
