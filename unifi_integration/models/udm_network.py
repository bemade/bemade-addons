# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UdmNetwork(models.Model):
    """Represents a network in the UniFi system
    
    This model stores network configuration for both UDM/UDR and software controllers.
    Each network can be associated with a VLAN and contains DHCP configuration.
    
    Networks are linked to a specific site and are automatically deleted when
    the site is deleted (cascade).
    """
    _name = 'udm.network'
    _description = 'UniFi Network'
    
    site_id = fields.Many2one('udm.site', string='Site', required=True, ondelete='cascade',
                             help='Site this network belongs to')
    name = fields.Char(string='Name', required=True,
                      help='Network name')
    purpose = fields.Selection([
        ('corporate', 'Corporate'),
        ('guest', 'Guest'),
        ('iot', 'IoT'),
        ('other', 'Other')
    ], string='Purpose', required=True, default='corporate',
        help='Network purpose/type')
    subnet = fields.Char(string='Subnet', required=True,
                        help='Network subnet in CIDR format (e.g. 192.168.1.0/24)')
    vlan_id_number = fields.Integer(string='VLAN ID',
                                   help='VLAN ID number (1-4094)')
    vlan_id = fields.Many2one('udm.vlan', string='VLAN',
                             compute='_compute_vlan_id', store=True,
                             help='Associated VLAN configuration')
    dhcp_enabled = fields.Boolean(string='DHCP Enabled', default=True,
                                 help='Enable DHCP server for this network')
    dhcp_start = fields.Char(string='DHCP Start',
                            help='Start of DHCP range')
    dhcp_stop = fields.Char(string='DHCP Stop',
                           help='End of DHCP range')
    domain_name = fields.Char(string='Domain Name',
                             help='Network domain name')
    raw_data = fields.Text(string='Raw Data',
                          help='Raw network configuration data in JSON format')
    
    # Statistics
    device_count = fields.Integer(string='Device Count', compute='_compute_device_count')
    
    @api.depends('vlan_id_number', 'site_id')
    def _compute_vlan_id(self):
        """Compute the associated VLAN based on the VLAN ID number
        
        This method searches for a VLAN with matching ID in the same site.
        The VLAN ID is stored and updated automatically when either the
        VLAN ID number or site changes.
        """
        for record in self:
            if not record.vlan_id_number or not record.site_id:
                record.vlan_id = False
                continue
                
            vlan = self.env['udm.vlan'].search([
                ('site_id', '=', record.site_id.id),
                ('vlan_id', '=', record.vlan_id_number)
            ], limit=1)
            
            record.vlan_id = vlan.id if vlan else False
    
    def _compute_device_count(self):
        for record in self:
            # This function would be more accurate if devices were linked to networks
            # For now, this is just an example
            record.device_count = 0


class UdmVlan(models.Model):
    """Represents a VLAN in the UniFi system
    
    This model stores VLAN configurations for both UDM/UDR and software controllers.
    VLANs are used to segment network traffic and can be associated with multiple
    networks.
    
    VLANs are linked to a specific site and are automatically deleted when
    the site is deleted (cascade).
    """
    _name = 'udm.vlan'
    _description = 'UniFi VLAN'
    
    site_id = fields.Many2one('udm.site', string='Site', required=True, ondelete='cascade',
                             help='Site this VLAN belongs to')
    vlan_id = fields.Integer(string='VLAN ID', required=True,
                            help='VLAN ID number (1-4094)')
    name = fields.Char(string='Name', required=True,
                      help='VLAN name')
    enabled = fields.Boolean(string='Enabled', default=True,
                           help='VLAN status')
    raw_data = fields.Text(string='Raw Data',
                          help='Raw VLAN configuration data in JSON format')
    
    # Reverse relations
    network_ids = fields.One2many('udm.network', 'vlan_id', string='Networks')
    network_count = fields.Integer(compute='_compute_network_count')
    
    @api.depends('network_ids')
    def _compute_network_count(self):
        for record in self:
            record.network_count = len(record.network_ids)
