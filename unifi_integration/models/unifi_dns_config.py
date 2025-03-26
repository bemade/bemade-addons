# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import json

_logger = logging.getLogger(__name__)

class UnifiDnsConfig(models.Model):
    """Configuration DNS pour le système UniFi
    
    Ce modèle stocke la configuration DNS pour les contrôleurs UniFi.
    Il gère les paramètres DNS comme les serveurs personnalisés et le filtrage de contenu.
    
    La configuration DNS est liée à un site spécifique et est automatiquement supprimée
    lorsque le site est supprimé (cascade).
    """
    _name = 'unifi.dns.config'
    _description = 'UniFi DNS Configuration'
    
    site_id = fields.Many2one(
        comodel_name='unifi.site', 
        string='Site', 
        required=True,
        ondelete='cascade',
        help='Site this DNS configuration belongs to'
    )
    
    enabled = fields.Boolean(
        string='Enabled', 
        default=True,
        help='Enable DNS server'
    )
    
    filters_enabled = fields.Boolean(
        string='Content Filtering Enabled', 
        default=False,
        help='Enable DNS content filtering'
    )
    
    custom_dns = fields.Char(
        string='Custom DNS Servers',
        help='Comma-separated list of custom DNS servers'
    )
    
    forwarding_enabled = fields.Boolean(
        string='DNS Forwarding Enabled',
        default=False,
        help='Enable DNS query forwarding'
    )
    
    mdns_enabled = fields.Boolean(
        string='mDNS Enabled',
        default=False,
        help='Enable multicast DNS (mDNS)'
    )
    
    unifi_id = fields.Char(
        string='UniFi ID',
        help='ID of this DNS configuration in the UniFi system'
    )
    
    last_sync = fields.Datetime(
        string='Last Synchronization',
        help='Last time this DNS configuration was synchronized with the UniFi system'
    )
    
    raw_data = fields.Text(
        string='Raw Data',
        help='Raw DNS configuration data in JSON format'
    )
    
    @api.constrains('custom_dns')
    def _check_custom_dns_format(self):
        """Vérifie que les serveurs DNS personnalisés sont au format valide"""
        for record in self:
            if not record.custom_dns:
                continue
                
            dns_servers = record.custom_dns.split(',')
            for server in dns_servers:
                server = server.strip()
                # Validation simple pour IPv4
                if server:
                    ip_parts = server.split('.')
                    if len(ip_parts) != 4:
                        raise ValidationError(_("Les serveurs DNS doivent être au format IPv4 (x.x.x.x)."))
                    
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
            name = f"Configuration DNS - {record.site_id.name}"
            result.append((record.id, name))
        return result
    
    def sync_from_unifi(self):
        """Synchronise les données depuis le système UniFi"""
        for record in self:
            site = record.site_id
            if not site:
                continue
                
            _logger.info("Synchronizing DNS configuration from UniFi site %s", site.name)
            
            # La synchronisation dépend du type d'API du site
            if site.api_type == 'controller':
                # TODO: Implémenter la synchronisation depuis l'API Controller
                pass
            elif site.api_type == 'site_manager':
                # TODO: Implémenter la synchronisation depuis l'API Site Manager
                pass
            
            record.last_sync = fields.Datetime.now()
    
    def push_to_unifi(self):
        """Pousse les modifications vers le système UniFi"""
        for record in self:
            site = record.site_id
            if not site:
                continue
                
            _logger.info("Pushing DNS configuration to UniFi site %s", site.name)
            
            # La synchronisation dépend du type d'API du site
            if site.api_type == 'controller':
                # TODO: Implémenter la synchronisation vers l'API Controller
                pass
            elif site.api_type == 'site_manager':
                # TODO: Implémenter la synchronisation vers l'API Site Manager
                pass
            
            record.last_sync = fields.Datetime.now()
