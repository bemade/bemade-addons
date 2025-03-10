# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UdmSettings(models.Model):
    """Configuration générale de l'UDM Pro"""
    _name = 'udm.settings'
    _description = 'UDM Pro Settings'
    
    config_id = fields.Many2one('udm.configuration', string='Configuration', ondelete='cascade')
    timezone = fields.Char(string='Timezone')
    ntp_servers = fields.Char(string='NTP Servers')
    dns_servers = fields.Char(string='DNS Servers')
    raw_data = fields.Text(string='Raw Data')
    
    # Champs calculés
    ntp_server_list = fields.Many2many('ir.model.data', string='NTP Server List', 
                                     compute='_compute_server_lists')
    dns_server_list = fields.Many2many('ir.model.data', string='DNS Server List',
                                     compute='_compute_server_lists')
    
    @api.depends('ntp_servers', 'dns_servers')
    def _compute_server_lists(self):
        for record in self:
            # Conversion des chaînes de caractères en listes pour l'affichage dans l'interface
            record.ntp_server_list = False  # Ceci est un champ technique pour l'UI
            record.dns_server_list = False  # Ceci est un champ technique pour l'UI
