# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging


_logger = logging.getLogger(__name__)

class UnifiRouting(models.Model):
    """Route pour le système UniFi
    
    Ce modèle stocke les routes individuelles pour les contrôleurs UniFi.
    Il gère les routes statiques et dynamiques.
    
    Les routes sont liées à un site spécifique et sont automatiquement supprimées
    lorsque le site est supprimé (cascade).
    """
    _name = 'unifi.routing'
    _description = 'UniFi Route'
    _rec_name = 'destination'
    _order = 'destination'
    
    site_id = fields.Many2one(
        comodel_name='unifi.site', 
        string='Site', 
        required=True,
        ondelete='cascade',
        help='Site this route belongs to'
    )
    
    destination = fields.Char(
        string='Destination',
        required=True,
        help='Destination network in CIDR format (e.g., 192.168.1.0/24)'
    )
    
    gateway = fields.Char(
        string='Gateway',
        required=True,
        help='Next hop IP address'
    )
    
    interface = fields.Char(
        string='Interface',
        help='Network interface for this route'
    )
    
    metric = fields.Integer(
        string='Metric',
        default=0,
        help='Route metric (priority)'
    )
    
    route_type = fields.Selection(
        selection=[
            ('static', 'Static'),
            ('dynamic', 'Dynamic'),
        ],
        string='Route Type',
        default='static',
        help='Type of route'
    )
    
    protocol = fields.Selection(
        selection=[
            ('static', 'Static'),
            ('ospf', 'OSPF'),
            ('bgp', 'BGP'),
            ('rip', 'RIP'),
        ],
        string='Protocol',
        default='static',
        help='Routing protocol'
    )
    
    enabled = fields.Boolean(
        string='Enabled',
        default=True,
        help='Whether this route is active'
    )
    
    description = fields.Text(
        string='Description',
        help='Optional description for this route'
    )
    
    unifi_id = fields.Char(
        string='UniFi ID',
        help='ID of this route in the UniFi system'
    )
    
    last_sync = fields.Datetime(
        string='Last Synchronization',
        help='Last time this route was synchronized with the UniFi system'
    )
    
    raw_data = fields.Text(
        string='Raw Data',
        help='Raw route data in JSON format'
    )
    
    @api.constrains('destination')
    def _check_destination_format(self):
        """Vérifie que la destination est au format CIDR valide"""
        for record in self:
            # Validation simple pour le format CIDR
            if '/' not in record.destination:
                raise ValidationError(_("La destination doit être au format CIDR (réseau/préfixe)."))
            
            network, prefix = record.destination.split('/')
            
            # Validation simple pour IPv4
            ip_parts = network.split('.')
            if len(ip_parts) != 4:
                raise ValidationError(_("L'adresse réseau doit être au format IPv4 (x.x.x.x)."))
            
            for part in ip_parts:
                try:
                    num = int(part)
                    if num < 0 or num > 255:
                        raise ValidationError(_("Chaque partie de l'adresse IP doit être comprise entre 0 et 255."))
                except ValueError as exc:
                    raise ValidationError(_("L'adresse IP doit contenir uniquement des nombres.")) from exc
            
            # Validation du préfixe
            try:
                prefix_num = int(prefix)
                if prefix_num < 0 or prefix_num > 32:
                    raise ValidationError(_("Le préfixe doit être compris entre 0 et 32."))
            except ValueError as exc:
                raise ValidationError(_("Le préfixe doit être un nombre.")) from exc
    
    @api.constrains('gateway')
    def _check_gateway_format(self):
        """Vérifie que la passerelle est au format IP valide"""
        for record in self:
            # Validation simple pour IPv4
            ip_parts = record.gateway.split('.')
            if len(ip_parts) != 4:
                raise ValidationError(_("La passerelle doit être au format IPv4 (x.x.x.x)."))
            
            for part in ip_parts:
                try:
                    num = int(part)
                    if num < 0 or num > 255:
                        raise ValidationError(_("Chaque partie de l'adresse IP doit être comprise entre 0 et 255."))
                except ValueError as exc:
                    raise ValidationError(_("L'adresse IP doit contenir uniquement des nombres.")) from exc
    
    def name_get(self):
        """Personnalise l'affichage du nom des enregistrements"""
        result = []
        for record in self:
            name = f"{record.destination} via {record.gateway}"
            result.append((record.id, name))
        return result
    
    def sync_from_unifi(self):
        """Synchronise les données depuis le système UniFi"""
        for record in self:
            site = record.site_id
            if not site:
                continue
                
            _logger.info("Synchronizing route %s from UniFi site %s", record.destination, site.name)
            
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
                
            _logger.info("Pushing route %s to UniFi site %s", record.destination, site.name)
            
            # La synchronisation dépend du type d'API du site
            if site.api_type == 'controller':
                # TODO(dev): Implémenter la synchronisation vers l'API Controller
                pass
            elif site.api_type == 'site_manager':
                # TODO(dev): Implémenter la synchronisation vers l'API Site Manager
                pass
            
            record.last_sync = fields.Datetime.now()
