# -*- coding: utf-8 -*-

import json
import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class UnifiSystemInfo(models.Model):
    """System information of the UniFi device"""
    _name = 'unifi.system.info'
    _description = 'UniFi System Information'
    _rec_name = 'hostname'
    
    @api.onchange('uptime')
    def _onchange_uptime(self):
        """Update human readable uptime when uptime changes"""
        if self.uptime:
            self._compute_uptime_human()
    
    site_id = fields.Many2one(
        comodel_name='unifi.site', 
        string='Site', 
        required=True,
        ondelete='cascade',
        help='Site this system information belongs to'
    )
    
    # Basic system information
    hostname = fields.Char(string='Hostname')
    version = fields.Char(string='Firmware Version')
    model = fields.Char(string='Model')
    uptime = fields.Integer(string='Uptime (seconds)')
    uptime_human = fields.Char(string='Uptime', compute='_compute_uptime_human')
    serial = fields.Char(string='Serial Number')
    mac_address = fields.Char(string='MAC Address')
    
    # Additional fields for UniFi system info
    device_id = fields.Char(string='Device ID')
    ip_address = fields.Char(string='IP Address')
    cpu_usage = fields.Float(string='CPU Usage (%)')
    memory_usage = fields.Float(string='Memory Usage (%)')
    temperature = fields.Float(string='Temperature (°C)')
    
    # Audit fields
    created_at = fields.Datetime(string='Created At', default=fields.Datetime.now, readonly=True)
    updated_at = fields.Datetime(string='Updated At', default=fields.Datetime.now, readonly=True)
    last_sync = fields.Datetime(string='Last Sync', readonly=True)
    
    # Raw data for debugging and future extensions
    raw_data = fields.Text(string='Raw Data')
    
    @api.depends('uptime')
    def _compute_uptime_human(self):
        for record in self:
            if not record.uptime:
                record.uptime_human = 'Unknown'
            else:
                days, remainder = divmod(record.uptime, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                parts = []
                if days > 0:
                    parts.append(f"{days} day{'s' if days != 1 else ''}")
                if hours > 0:
                    parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
                if minutes > 0:
                    parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
                if seconds > 0 or not parts:
                    parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
                
                record.uptime_human = ', '.join(parts)
    
    def create_or_update_from_data(self, site, system_data):
        """Create or update system info from API data"""
        # Check if system info already exists for this site
        system_info = self.search([('site_id', '=', site.id)], limit=1)
        
        vals = {
            'site_id': site.id,
            'hostname': system_data.get('hostname'),
            'version': system_data.get('version'),
            'model': system_data.get('model'),
            'uptime': system_data.get('uptime'),
            'serial': system_data.get('serial'),
            'mac_address': system_data.get('mac'),
            'device_id': system_data.get('device_id'),
            'ip_address': system_data.get('ip'),
            'cpu_usage': system_data.get('cpu_usage'),
            'memory_usage': system_data.get('mem_usage'),
            'temperature': system_data.get('temperature'),
            'raw_data': json.dumps(system_data, indent=2),
            'updated_at': fields.Datetime.now(),
            'last_sync': fields.Datetime.now(),
        }
        
        if system_info:
            system_info.write(vals)
            _logger.info("Updated system info for site %s", site.name)
            return system_info
        else:
            new_system_info = self.create(vals)
            _logger.info("Created new system info for site %s", site.name)
            return new_system_info
