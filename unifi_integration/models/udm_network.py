# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UdmNetwork(models.Model):
    """Représentation d'un réseau dans l'UDM Pro"""
    _name = 'udm.network'
    _description = 'UDM Pro Network'
    
    config_id = fields.Many2one('udm.configuration', string='Configuration', ondelete='cascade')
    name = fields.Char(string='Name', required=True)
    purpose = fields.Char(string='Purpose')
    subnet = fields.Char(string='Subnet')
    vlan_id_number = fields.Integer(string='VLAN ID')
    vlan_id = fields.Many2one('udm.vlan', string='VLAN', compute='_compute_vlan_id', store=True)
    dhcp_enabled = fields.Boolean(string='DHCP Enabled', default=False)
    dhcp_start = fields.Char(string='DHCP Start')
    dhcp_stop = fields.Char(string='DHCP Stop')
    domain_name = fields.Char(string='Domain Name')
    raw_data = fields.Text(string='Raw Data')
    
    # Statistiques
    device_count = fields.Integer(string='Device Count', compute='_compute_device_count')
    
    @api.depends('vlan_id_number', 'config_id')
    def _compute_vlan_id(self):
        for record in self:
            if not record.vlan_id_number or not record.config_id:
                record.vlan_id = False
                continue
                
            vlan = self.env['udm.vlan'].search([
                ('config_id', '=', record.config_id.id),
                ('vlan_id', '=', record.vlan_id_number)
            ], limit=1)
            
            record.vlan_id = vlan.id if vlan else False
    
    def _compute_device_count(self):
        for record in self:
            # Cette fonction serait plus précise si les périphériques étaient liés aux réseaux
            # Pour l'instant, c'est juste un exemple
            record.device_count = 0


class UdmVLAN(models.Model):
    """Représentation d'un VLAN dans l'UDM Pro"""
    _name = 'udm.vlan'
    _description = 'UDM Pro VLAN'
    
    config_id = fields.Many2one('udm.configuration', string='Configuration', ondelete='cascade')
    vlan_id = fields.Integer(string='VLAN ID', required=True)
    name = fields.Char(string='Name', required=True)
    enabled = fields.Boolean(string='Enabled', default=True)
    raw_data = fields.Text(string='Raw Data')
    
    # Relations inverses
    network_ids = fields.One2many('udm.network', 'vlan_id', string='Networks')
    network_count = fields.Integer(compute='_compute_network_count')
    
    @api.depends('network_ids')
    def _compute_network_count(self):
        for record in self:
            record.network_count = len(record.network_ids)
