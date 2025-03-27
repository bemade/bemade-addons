# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import json

_logger = logging.getLogger(__name__)

class UnifiDns(models.Model):
    """Entrée DNS pour le système UniFi
    
    Ce modèle stocke les entrées DNS pour les contrôleurs UniFi.
    Il gère les enregistrements DNS comme les mappages nom d'hôte -> adresse IP.
    
    Les entrées DNS sont liées à un site spécifique et sont automatiquement supprimées
    lorsque le site est supprimé (cascade).
    """
    _name = 'unifi.dns'
    _description = 'UniFi DNS Entry'
    _rec_name = 'hostname'
    _order = 'hostname'
    
    site_id = fields.Many2one(
        comodel_name='unifi.site', 
        string='Site', 
        required=True,
        ondelete='cascade',
        help='Site this DNS entry belongs to'
    )
    
    hostname = fields.Char(
        string='Hostname',
        required=True,
        help='Hostname for this DNS entry'
    )
    
    ip_address = fields.Char(
        string='IP Address',
        required=True,
        help='IP address for this hostname'
    )
    
    description = fields.Text(
        string='Description',
        help='Optional description for this DNS entry'
    )
    
    enabled = fields.Boolean(
        string='Enabled',
        default=True,
        help='Whether this DNS entry is active'
    )
    
    entry_type = fields.Selection(
        selection=[
            ('static', 'Static'),
            ('dynamic', 'Dynamic'),
        ],
        string='Entry Type',
        default='static',
        help='Type of DNS entry'
    )
    
    unifi_id = fields.Char(
        string='UniFi ID',
        help='ID of this DNS entry in the UniFi system'
    )
    
    last_sync = fields.Datetime(
        string='Last Synchronization',
        help='Last time this DNS entry was synchronized with the UniFi system'
    )
    
    raw_data = fields.Text(
        string='Raw Data',
        help='Raw DNS entry data in JSON format'
    )
    
    @api.constrains('hostname', 'site_id')
    def _check_hostname_unique(self):
        """Vérifie que le nom d'hôte est unique pour un site donné"""
        for record in self:
            domain = [
                ('hostname', '=', record.hostname),
                ('site_id', '=', record.site_id.id),
                ('id', '!=', record.id)
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(_("Le nom d'hôte doit être unique pour un site donné."))
    
    @api.constrains('ip_address')
    def _check_ip_address_format(self):
        """Vérifie que l'adresse IP est au format valide"""
        for record in self:
            # Validation simple pour IPv4
            ip_parts = record.ip_address.split('.')
            if len(ip_parts) != 4:
                raise ValidationError(_("L'adresse IP doit être au format IPv4 (x.x.x.x)."))
            
            for part in ip_parts:
                try:
                    num = int(part)
                    if num < 0 or num > 255:
                        raise ValidationError(_("Chaque partie de l'adresse IP doit être comprise entre 0 et 255."))
                except ValueError:
                    raise ValidationError(_("L'adresse IP doit contenir uniquement des nombres."))
    
    def name_get(self):
        """Personnalise l'affichage du nom des enregistrements"""
        result = []
        for record in self:
            name = f"{record.hostname} ({record.ip_address})"
            result.append((record.id, name))
        return result
    
    def sync_from_unifi(self):
        """Synchronise les données depuis le système UniFi"""
        for record in self:
            site = record.site_id
            if not site:
                continue
                
            _logger.info("Synchronizing DNS entry %s from UniFi site %s", record.hostname, site.name)
            
            # La synchronisation dépend du type d'API du site
            if site.api_type == 'controller':
                # TODO: Implémenter la synchronisation depuis l'API Controller
                pass
            elif site.api_type == 'site_manager':
                # TODO: Implémenter la synchronisation depuis l'API Site Manager
                pass
            
            record.last_sync = fields.Datetime.now()
    
    @api.model
    def create_or_update_from_data(self, site, dns_data):
        """Create or update DNS entry from UniFi API data
        
        Args:
            site (unifi.site): Site record
            dns_data (dict): DNS entry data from UniFi API
            
        Returns:
            unifi.dns: Created or updated DNS entry record
        """
        _logger.info("Creating or updating DNS entry from data: %s", dns_data)
        
        # Extract required fields
        hostname = dns_data.get('hostname')
        ip_address = dns_data.get('ip_address')
        unifi_id = dns_data.get('id') or dns_data.get('_id')
        
        if not hostname or not ip_address:
            _logger.warning("Missing required fields in DNS data: %s", dns_data)
            return False
        
        # Search for existing DNS entry
        domain = [
            ('site_id', '=', site.id),
            '|',
            ('hostname', '=', hostname),
            ('unifi_id', '=', unifi_id)
        ]
        
        existing = self.search(domain, limit=1)
        
        # Prepare values for create/write
        vals = {
            'hostname': hostname,
            'ip_address': ip_address,
            'unifi_id': unifi_id,
            'description': dns_data.get('description', ''),
            'enabled': dns_data.get('enabled', True),
            'entry_type': dns_data.get('type', 'static'),
            'last_sync': fields.Datetime.now(),
            'raw_data': json.dumps(dns_data, indent=2) if dns_data else False
        }
        
        if existing:
            _logger.info("Updating existing DNS entry: %s", existing.hostname)
            existing.write(vals)
            return existing
        else:
            _logger.info("Creating new DNS entry: %s", hostname)
            vals['site_id'] = site.id
            return self.create(vals)
    
    def push_to_unifi(self):
        """Pousse les modifications vers le système UniFi"""
        for record in self:
            site = record.site_id
            if not site:
                continue
                
            _logger.info("Pushing DNS entry %s to UniFi site %s", record.hostname, site.name)
            
            # La synchronisation dépend du type d'API du site
            if site.api_type == 'controller':
                # TODO: Implémenter la synchronisation vers l'API Controller
                pass
            elif site.api_type == 'site_manager':
                # TODO: Implémenter la synchronisation vers l'API Site Manager
                pass
            
            record.last_sync = fields.Datetime.now()
