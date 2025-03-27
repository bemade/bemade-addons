# -*- coding: utf-8 -*-

# These imports will work in an Odoo environment, even if your IDE marks them as not found
# pylint: disable=import-error
from odoo import models, fields, api, _
from .unifi_common import UnifiCommonMixin
from odoo.exceptions import UserError, ValidationError
# pylint: enable=import-error

import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class UnifiNetwork(models.Model, UnifiCommonMixin):
    """Modèle pour gérer les réseaux UniFi
    
    Ce modèle représente les réseaux configurés dans les sites UniFi,
    qu'ils soient gérés par l'API Controller ou l'API Site Manager.
    """
    _name = 'unifi.network'
    _description = 'Réseau UniFi'
    _order = 'name'
    
    # Champs d'identification
    name = fields.Char(
        string='Nom',
        required=True,
        help='Nom du réseau'
    )
    
    network_id = fields.Char(
        string='ID Réseau',
        required=True,
        help='Identifiant unique du réseau dans le système UniFi'
    )
    
    # Champs de configuration réseau
    purpose = fields.Selection(
        selection=[
            ('corporate', 'Corporate'),
            ('guest', 'Guest'),
            ('wan', 'WAN'),
            ('lan', 'LAN'),
            ('vpn', 'VPN'),
            ('site-vpn', 'Site VPN'),
            ('remote-user-vpn', 'Remote User VPN'),
            ('vlan-only', 'VLAN Only'),
            ('other', 'Autre')
        ],
        string='Type',
        default='corporate',
        help='Type/objectif du réseau'
    )
    
    subnet = fields.Char(
        string='Sous-réseau',
        help='Sous-réseau au format CIDR (ex: 192.168.1.0/24)'
    )
    
    vlan_id = fields.Integer(
        string='ID VLAN',
        help='Identifiant du VLAN associé à ce réseau'
    )
    
    dhcp_enabled = fields.Boolean(
        string='DHCP Activé',
        default=True,
        help='Indique si le DHCP est activé pour ce réseau'
    )
    
    dhcp_start = fields.Char(
        string='Début DHCP',
        help='Adresse IP de début de la plage DHCP'
    )
    
    dhcp_stop = fields.Char(
        string='Fin DHCP',
        help='Adresse IP de fin de la plage DHCP'
    )
    
    dhcp_lease_time = fields.Integer(
        string='Durée du bail DHCP',
        default=86400,  # 24 heures en secondes
        help='Durée du bail DHCP en secondes'
    )
    
    domain_name = fields.Char(
        string='Nom de domaine',
        help='Nom de domaine pour ce réseau'
    )
    
    dns_servers = fields.Char(
        string='Serveurs DNS',
        help='Liste des serveurs DNS séparés par des virgules'
    )
    
    enabled = fields.Boolean(
        string='Activé',
        default=True,
        help='Indique si le réseau est actif'
    )
    
    # Champs pour la gestion des invités (si applicable)
    is_guest = fields.Boolean(
        string='Réseau invité',
        default=False,
        help='Indique si ce réseau est configuré pour les invités'
    )
    
    guest_portal_enabled = fields.Boolean(
        string='Portail invité activé',
        default=False,
        help='Indique si le portail captif est activé pour ce réseau'
    )
    
    # Champs pour le suivi et l'audit
    created_at = fields.Datetime(
        string='Créé le',
        default=fields.Datetime.now,
        help='Date de création du réseau dans Odoo'
    )
    
    updated_at = fields.Datetime(
        string='Mis à jour le',
        help='Date de dernière mise à jour du réseau dans Odoo'
    )
    
    last_sync = fields.Datetime(
        string='Dernière synchronisation',
        help='Date de la dernière synchronisation avec l\'API UniFi'
    )
    
    # Stockage des données brutes
    raw_data = fields.Text(
        string='Données brutes',
        help='Données brutes du réseau au format JSON'
    )
    
    raw_data_json = fields.Text(
        string='Données brutes (JSON)',
        compute='_compute_raw_data_json',
        help='Données brutes du réseau au format JSON formaté'
    )
    
    @api.depends('raw_data')
    def _compute_raw_data_json(self):
        for record in self:
            record.raw_data_json = self.format_raw_data_json(record.raw_data)
    
    # Relations
    site_id = fields.Many2one(
        comodel_name='unifi.site',
        string='Site',
        required=True,
        ondelete='cascade',
        help='Site UniFi auquel appartient ce réseau'
    )
    
    # Champs calculés
    ip_subnet = fields.Char(
        string='Sous-réseau IP',
        compute='_compute_ip_subnet',
        store=True,
        help='Adresse IP du sous-réseau'
    )
    
    netmask = fields.Char(
        string='Masque de sous-réseau',
        compute='_compute_ip_subnet',
        store=True,
        help='Masque de sous-réseau'
    )
    
    @api.depends('subnet')
    def _compute_ip_subnet(self):
        """Calcule l'adresse IP du sous-réseau et le masque à partir du CIDR"""
        for network in self:
            if network.subnet:
                try:
                    # Séparation de l'adresse IP et du préfixe CIDR
                    parts = network.subnet.split('/')
                    if len(parts) == 2:
                        ip_address = parts[0]
                        prefix = int(parts[1])
                        
                        # Calcul du masque de sous-réseau à partir du préfixe
                        mask_bits = '1' * prefix + '0' * (32 - prefix)
                        mask_int = int(mask_bits, 2)
                        mask_octets = [(mask_int >> i) & 0xFF for i in (24, 16, 8, 0)]
                        mask = '.'.join(map(str, mask_octets))
                        
                        network.ip_subnet = ip_address
                        network.netmask = mask
                    else:
                        network.ip_subnet = False
                        network.netmask = False
                except Exception as e:
                    _logger.error(f"Erreur lors du calcul du sous-réseau: {str(e)}")
                    network.ip_subnet = False
                    network.netmask = False
            else:
                network.ip_subnet = False
                network.netmask = False
    
    @api.model
    def create_or_update_from_data(self, site, network_data):
        """Crée ou met à jour un réseau à partir des données de l'API
        
        Args:
            site: L'enregistrement du site UniFi
            network_data: Données du réseau provenant de l'API
            
        Returns:
            record: L'enregistrement du réseau créé ou mis à jour
        """
        # Extraction de l'identifiant du réseau
        network_id = network_data.get('_id') or network_data.get('id')
        if not network_id:
            _logger.error("Impossible de créer/mettre à jour le réseau: identifiant manquant")
            return False
        
        # Recherche d'un réseau existant avec cet identifiant
        existing_network = self.search([
            ('network_id', '=', network_id),
            ('site_id', '=', site.id)
        ], limit=1)
        
        # Préparation des valeurs pour la création/mise à jour
        vals = {
            'network_id': network_id,
            'name': network_data.get('name', f"Réseau {network_id}"),
            'site_id': site.id,
            'purpose': network_data.get('purpose', 'other'),
            'subnet': network_data.get('subnet'),
            'vlan_id': network_data.get('vlan_id') or network_data.get('vlan'),
            'dhcp_enabled': network_data.get('dhcp_enabled', True),
            'dhcp_start': network_data.get('dhcp_start') or network_data.get('dhcpd_start'),
            'dhcp_stop': network_data.get('dhcp_stop') or network_data.get('dhcpd_stop'),
            'dhcp_lease_time': network_data.get('dhcp_lease_time') or network_data.get('dhcpd_leasetime', 86400),
            'domain_name': network_data.get('domain_name'),
            'dns_servers': network_data.get('dns_servers') or network_data.get('dns1'),
            'enabled': network_data.get('enabled', True),
            'is_guest': network_data.get('is_guest', False) or network_data.get('purpose') == 'guest',
            'guest_portal_enabled': network_data.get('guest_portal_enabled', False),
            'last_sync': fields.Datetime.now(),
            'raw_data': json.dumps(network_data)
        }
        
        if existing_network:
            # Mise à jour du réseau existant
            vals['updated_at'] = fields.Datetime.now()
            existing_network.write(vals)
            return existing_network
        else:
            # Création d'un nouveau réseau
            return self.create(vals)
    
    def sync_networks(self):
        """Synchronise les réseaux depuis l'API UniFi
        
        Cette méthode est conçue pour être appelée depuis un bouton dans l'interface utilisateur.
        Elle utilise le site associé à l'enregistrement en cours.
        
        Returns:
            bool: True si la synchronisation a réussi, False sinon
        """
        self.ensure_one()
        
        # Utiliser le site associé à ce réseau
        site = self.site_id
        if not site:
            _logger.error("Impossible de synchroniser: aucun site associé à ce réseau")
            return False
        
        # Déterminer quelle méthode utiliser en fonction du type d'API
        if site.api_type == 'controller':
            return self._sync_networks_controller(site)
        elif site.api_type == 'site_manager':
            return self._sync_networks_site_manager(site)
    
    def sync_networks_from_list(self):
        """Synchronise tous les réseaux du site actuel depuis la vue liste
        
        Cette méthode vérifie si tous les réseaux affichés appartiennent au même site,
        puis appelle la méthode de synchronisation appropriée.
        
        Returns:
            dict: Action de rafraîchissement de la vue ou notification d'erreur
        """
        # Vérifier si tous les réseaux appartiennent au même site
        sites = self.mapped('site_id')
        
        if not sites:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('Aucun site associé aux réseaux sélectionnés.'),
                    'sticky': False,
                    'type': 'danger',
                }
            }
        
        if len(sites) > 1:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('Les réseaux sélectionnés appartiennent à différents sites. Veuillez filtrer par site.'),
                    'sticky': False,
                    'type': 'danger',
                }
            }
        
        # Tous les réseaux appartiennent au même site, appeler la méthode de synchronisation
        site = sites[0]
        
        # Déterminer quelle méthode utiliser en fonction du type d'API
        try:
            if site.api_type == 'controller':
                self._sync_networks_controller(site)
            elif site.api_type == 'site_manager':
                self._sync_networks_site_manager(site)
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Erreur'),
                        'message': _('Type d\'API non pris en charge.'),
                        'sticky': False,
                        'type': 'danger',
                    }
                }
                
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Succès'),
                    'message': _('Synchronisation des réseaux terminée avec succès.'),
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _(f'Erreur lors de la synchronisation: {str(e)}'),
                    'sticky': False,
                    'type': 'danger',
                }
            }
    
    @api.model
    def sync_site_networks(self, site_id):
        """Synchronise tous les réseaux d'un site spécifique
        
        Cette méthode est conçue pour être appelée depuis un bouton dans la vue liste
        lorsque tous les réseaux affichés appartiennent au même site.
        
        Args:
            site_id: ID du site dont les réseaux doivent être synchronisés
            
        Returns:
            dict: Action de rafraîchissement de la vue
        """
        # Récupérer le site
        site = self.env['unifi.site'].browse(site_id)
        if not site.exists():
            raise UserError(_("Le site sélectionné n'existe pas."))
        
        # Déterminer quelle méthode utiliser en fonction du type d'API
        if site.api_type == 'controller':
            self._sync_networks_controller(site)
        elif site.api_type == 'site_manager':
            self._sync_networks_site_manager(site)
        else:
            _logger.error(f"Type d'API non pris en charge: {site.api_type}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('Type d\'API non pris en charge.'),
                    'sticky': False,
                    'type': 'danger',
                }
            }
        
        # Retourner une action pour rafraîchir la vue
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    
    def _sync_networks_controller(self, site):
        """Synchronise les réseaux depuis l'API Controller
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            bool: True si la synchronisation a réussi, False sinon
        """
        # Obtenir les données des réseaux directement depuis le site
        networks_data = site._get_controller_network_data()
        if not networks_data:
            return False
        
        # Créer ou mettre à jour les réseaux
        for network_data in networks_data:
            self.create_or_update_from_data(site, network_data)
        
        return True
    
    def _sync_networks_site_manager(self, site):
        """Synchronise les réseaux depuis l'API Site Manager
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            bool: True si la synchronisation a réussi, False sinon
        """
        # Obtenir les données des réseaux directement depuis le site
        networks_data = site._get_site_manager_network_data()
        if not networks_data:
            return False
        
        # Créer ou mettre à jour les réseaux
        for network_data in networks_data:
            self.create_or_update_from_data(site, network_data)
        
        return True
