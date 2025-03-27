# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging


_logger = logging.getLogger(__name__)

class UnifiRoutingConfig(models.Model):
    """Configuration de routage pour le système UniFi
    
    Ce modèle stocke la configuration de routage pour les contrôleurs UniFi.
    Il gère les paramètres de routage comme OSPF et les routes statiques.
    
    La configuration de routage est liée à un site spécifique et est automatiquement supprimée
    lorsque le site est supprimé (cascade).
    """
    _name = 'unifi.routing.config'
    _description = 'UniFi Routing Configuration'
    
    site_id = fields.Many2one(
        comodel_name='unifi.site', 
        string='Site', 
        required=True,
        ondelete='cascade',
        help='Site this routing configuration belongs to'
    )
    
    name = fields.Char(
        string='Name',
        required=True,
        help='Name of the routing configuration'
    )
    
    ospf_enabled = fields.Boolean(
        string='OSPF Enabled',
        default=False,
        help='Enable OSPF routing'
    )
    
    static_routes = fields.Text(
        string='Static Routes',
        help='Comma-separated list of static routes in format: network/prefix via nexthop'
    )
    
    bgp_enabled = fields.Boolean(
        string='BGP Enabled',
        default=False,
        help='Enable BGP routing'
    )
    
    rip_enabled = fields.Boolean(
        string='RIP Enabled',
        default=False,
        help='Enable RIP routing'
    )
    
    unifi_id = fields.Char(
        string='UniFi ID',
        help='ID of this routing configuration in the UniFi system'
    )
    
    last_sync = fields.Datetime(
        string='Last Synchronization',
        help='Last time this routing configuration was synchronized with the UniFi system'
    )
    
    raw_data = fields.Text(
        string='Raw Data',
        help='Raw routing configuration data in JSON format'
    )
    
    def name_get(self):
        """Personnalise l'affichage du nom des enregistrements"""
        result = []
        for record in self:
            name = f"Configuration de routage - {record.site_id.name}"
            result.append((record.id, name))
        return result
    
    def sync_from_unifi(self):
        """Synchronise les données depuis le système UniFi"""
        for record in self:
            site = record.site_id
            if not site:
                continue
                
            _logger.info("Synchronizing routing configuration from UniFi site %s", site.name)
            
            # La synchronisation dépend du type d'API du site
            if site.api_type == 'controller':
                # TODO(dev): Implémenter la synchronisation depuis l'API Controller
                pass
            elif site.api_type == 'site_manager':
                # TODO(dev): Implémenter la synchronisation depuis l'API Site Manager
                pass
            
            record.last_sync = fields.Datetime.now()
    
    def push_to_unifi(self):
        """Pousse les modifications vers le système UniFi"""
        for record in self:
            site = record.site_id
            if not site:
                continue
                
            _logger.info("Pushing routing configuration to UniFi site %s", site.name)
            
            # La synchronisation dépend du type d'API du site
            if site.api_type == 'controller':
                # TODO(dev): Implémenter la synchronisation vers l'API Controller
                pass
            elif site.api_type == 'site_manager':
                # TODO(dev): Implémenter la synchronisation vers l'API Site Manager
                pass
            
            record.last_sync = fields.Datetime.now()
