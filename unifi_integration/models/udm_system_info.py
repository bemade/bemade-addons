# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UdmSystemInfo(models.Model):
    """System information of the UDM Pro"""
    _name = 'udm.system.info'
    _description = 'UDM Pro System Information'
    
    # Site this system information belongs to
    site_id = fields.Many2one('udm.site', string='Site', required=True, ondelete='cascade')
    hostname = fields.Char(string='Hostname')
    version = fields.Char(string='Firmware Version')
    model = fields.Char(string='Model')
    uptime = fields.Integer(string='Uptime (seconds)')
    uptime_human = fields.Char(string='Uptime', compute='_compute_uptime_human')
    serial = fields.Char(string='Serial Number')
    mac_address = fields.Char(string='MAC Address')
    raw_data = fields.Text(string='Raw Data')
    
    @api.depends('uptime')
    def _compute_uptime_human(self):
        for record in self:
            if not record.uptime:
                record.uptime_human = 'Unknown'
                continue
                
            days, remainder = divmod(record.uptime, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            parts = []
            if days:
                parts.append(f"{days} day{'s' if days != 1 else ''}")
            if hours:
                parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
            if minutes:
                parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
            if seconds or not parts:
                parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
                
            record.uptime_human = ', '.join(parts)
