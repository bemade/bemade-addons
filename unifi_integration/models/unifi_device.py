# -*- coding: utf-8 -*-

# These imports will work in an Odoo environment, even if your IDE marks them as not found
# pylint: disable=import-error
from odoo import models, fields, api
from odoo.tools.translate import _
# pylint: enable=import-error

import logging
import json
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class UnifiDevice(models.Model):
    """Modèle pour les appareils UniFi
    
    Ce modèle stocke les informations sur les appareils UniFi, tels que les points d'accès,
    les commutateurs et les passerelles. Il est synchronisé avec l'API UniFi.
    """
    _name = 'unifi.device'
    _description = 'UniFi Device'
    _order = 'name'
    
    name = fields.Char(
        string='Nom',
        required=True,
        index=True,
        help="Nom de l'appareil"
    )
    
    site_id = fields.Many2one(
        comodel_name='unifi.site',
        string='Site',
        required=True,
        ondelete='cascade',
        help="Site auquel cet appareil appartient"
    )
    
    mac_address = fields.Char(
        string='Adresse MAC',
        required=True,
        index=True,
        help="Adresse MAC de l'appareil"
    )
    
    ip_address = fields.Char(
        string='Adresse IP',
        help="Adresse IP de l'appareil"
    )
    
    model = fields.Char(
        string='Modèle',
        help="Modèle de l'appareil"
    )
    
    device_type = fields.Selection(
        selection=[
            ('uap', 'Point d\'accès'),
            ('usw', 'Commutateur'),
            ('ugw', 'Passerelle'),
            ('udm', 'Dream Machine'),
            ('other', 'Autre')
        ],
        string='Type d\'appareil',
        required=True,
        default='other',
        help="Type de l'appareil UniFi"
    )
    
    firmware_version = fields.Char(
        string='Version du firmware',
        help="Version actuelle du firmware de l'appareil"
    )
    
    status = fields.Selection(
        selection=[
            ('online', 'En ligne'),
            ('offline', 'Hors ligne'),
            ('pending', 'En attente'),
            ('provisioning', 'Provisionnement'),
            ('upgrading', 'Mise à niveau'),
            ('deleting', 'Suppression'),
            ('unknown', 'Inconnu')
        ],
        string='Statut',
        default='unknown',
        help="Statut actuel de l'appareil"
    )
    
    last_seen = fields.Datetime(
        string='Dernière connexion',
        help="Date et heure de la dernière connexion de l'appareil"
    )
    
    uptime = fields.Integer(
        string='Temps de fonctionnement',
        help="Temps de fonctionnement en secondes"
    )
    
    adoption_state = fields.Boolean(
        string='Adopté',
        default=False,
        help="Indique si l'appareil a été adopté par le contrôleur"
    )
    
    config_version = fields.Char(
        string='Version de configuration',
        help="Version de la configuration de l'appareil"
    )
    
    raw_data = fields.Text(
        string='Données brutes',
        help="Données JSON brutes de l'appareil provenant de l'API UniFi"
    )
    
    active = fields.Boolean(
        string='Actif',
        default=True,
        help="Indique si cet appareil est actuellement actif dans le système"
    )
    
    @api.model
    def create_from_api_data(self, site, device_data):
        """Crée ou met à jour un appareil à partir des données de l'API
        
        Args:
            site: Enregistrement du site UniFi
            device_data: Dictionnaire contenant les données de l'appareil de l'API
            
        Returns:
            L'enregistrement de l'appareil créé ou mis à jour
        """
        if not device_data.get('mac'):
            return False
            
        # Rechercher un appareil existant par MAC
        existing_device = self.search([
            ('site_id', '=', site.id),
            ('mac_address', '=', device_data.get('mac'))
        ], limit=1)
        
        # Préparer les valeurs pour la création/mise à jour
        vals = {
            'site_id': site.id,
            'mac_address': device_data.get('mac'),
            'name': device_data.get('name') or device_data.get('model') or device_data.get('mac'),
            'ip_address': device_data.get('ip'),
            'model': device_data.get('model'),
            'device_type': self._map_device_type(device_data.get('type')),
            'firmware_version': device_data.get('version'),
            'status': 'online' if device_data.get('state', 0) == 1 else 'offline',
            'last_seen': datetime.fromtimestamp(device_data.get('last_seen', 0) / 1000) if device_data.get('last_seen') else None,
            'uptime': device_data.get('uptime'),
            'adoption_state': device_data.get('adopted', False),
            'config_version': device_data.get('cfgversion'),
            'raw_data': json.dumps(device_data)
        }
        
        if existing_device:
            existing_device.write(vals)
            return existing_device
        else:
            return self.create(vals)
    
    def _map_device_type(self, api_type):
        """Mappe le type d'appareil de l'API au type de sélection
        
        Args:
            api_type: Type d'appareil provenant de l'API
            
        Returns:
            Type d'appareil correspondant dans la sélection
        """
        type_mapping = {
            'uap': 'uap',
            'usw': 'usw',
            'ugw': 'ugw',
            'udm': 'udm',
            'ubb': 'other',
            'usw-leaf': 'usw',
        }
        return type_mapping.get(api_type, 'other')
    
    def sync_from_unifi(self):
        """Synchronise les données de l'appareil depuis l'API UniFi
        
        Returns:
            True si la synchronisation a réussi, False sinon
        """
        self.ensure_one()
        
        if not self.site_id:
            return False
            
        # Utiliser la méthode appropriée du site pour obtenir les données de l'appareil
        device_data = self.site_id.get_device_data(self.mac_address)
        
        if not device_data:
            return False
            
        # Mettre à jour l'appareil avec les nouvelles données
        vals = {
            'name': device_data.get('name') or self.name,
            'ip_address': device_data.get('ip') or self.ip_address,
            'firmware_version': device_data.get('version'),
            'status': 'online' if device_data.get('state', 0) == 1 else 'offline',
            'last_seen': datetime.fromtimestamp(device_data.get('last_seen', 0) / 1000) if device_data.get('last_seen') else self.last_seen,
            'uptime': device_data.get('uptime'),
            'adoption_state': device_data.get('adopted', False),
            'config_version': device_data.get('cfgversion'),
            'raw_data': json.dumps(device_data)
        }
        
        self.write(vals)
        return True
