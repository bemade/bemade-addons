# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UdmDevice(models.Model):
    """Représentation d'un périphérique dans l'UDM Pro"""
    _name = 'udm.device'
    _description = 'UDM Pro Device'
    
    config_id = fields.Many2one('udm.configuration', string='Configuration', ondelete='cascade')
    name = fields.Char(string='Name')
    mac = fields.Char(string='MAC Address')
    ip = fields.Char(string='IP Address')
    device_type = fields.Char(string='Device Type')
    model = fields.Char(string='Model')
    last_seen = fields.Datetime(string='Last Seen')
    raw_data = fields.Text(string='Raw Data')
    
    # Champs calculés
    status = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('unknown', 'Unknown')
    ], string='Status', compute='_compute_status', store=True)
    
    @api.depends('last_seen')
    def _compute_status(self):
        # Calcul du statut basé sur la dernière fois où le périphérique a été vu
        # Ceci est un exemple simplifié
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
