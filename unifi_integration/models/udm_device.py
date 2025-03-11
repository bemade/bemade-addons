# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UdmDevice(models.Model):
    """Represents a network device in the UniFi system
    
    This model stores information about devices connected to the network,
    including both UniFi devices (APs, switches) and client devices.
    
    Devices are linked to a specific site and are automatically deleted when
    the site is deleted (cascade).
    """
    _name = 'udm.device'
    _description = 'UniFi Device'
    _order = 'last_seen desc'  # Most recently seen devices first
    
    site_id = fields.Many2one('udm.site', string='Site', required=True,
                             ondelete='cascade',
                             help='Site this device belongs to')
    name = fields.Char(string='Name',
                      help='Device name or hostname')
    mac_address = fields.Char(string='MAC Address', required=True,
                     help='Device MAC address')
    ip_address = fields.Char(string='IP Address',
                     help='Current IP address')
    device_type = fields.Selection([
        ('uap', 'Access Point'),
        ('usw', 'Switch'),
        ('ugw', 'Gateway'),
        ('udm', 'Dream Machine'),
        ('client', 'Client Device'),
        ('other', 'Other')
    ], string='Device Type', required=True, default='client',
        help='Type of device')
    model = fields.Char(string='Model',
                       help='Device model name')
    last_seen = fields.Datetime(string='Last Seen',
                               help='Last time the device was seen online')
    raw_data = fields.Text(string='Raw Data',
                          help='Raw device data in JSON format')
    
    # Computed fields
    status = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('unknown', 'Unknown')
    ], string='Status', compute='_compute_status', store=True)
    
    @api.depends('last_seen')
    def _compute_status(self):
        """Compute device online status based on last seen timestamp
        
        Status is determined by comparing the last_seen timestamp with current time:
        - Online: seen within last 10 minutes
        - Offline: not seen for more than 10 minutes
        - Unknown: never seen (no last_seen timestamp)
        """
        for record in self:
            if not record.last_seen:
                record.status = 'unknown'
                continue
                
            from datetime import datetime, timedelta
            now = fields.Datetime.now()
            time_diff = now - record.last_seen
            
            if time_diff <= timedelta(minutes=10):
                record.status = 'online'
            else:
                record.status = 'offline'
