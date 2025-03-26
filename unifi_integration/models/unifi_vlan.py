# -*- coding: utf-8 -*-

import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class UnifiVLAN(models.Model):
    """Modèle pour gérer les VLANs UniFi
    
    Ce modèle représente les VLANs configurés dans les sites UniFi.
    Il permet de stocker et gérer les informations des VLANs depuis les API Controller et Site Manager.
    """
    _name = 'unifi.vlan'
    _description = 'UniFi VLAN'
    _order = 'vlan_id'
    
    # Champs d'identification
    name = fields.Char(
        string='Nom',
        required=True,
        help='Nom du VLAN'
    )
    
    vlan_id = fields.Integer(
        string='ID VLAN',
        required=True,
        help='Identifiant numérique du VLAN'
    )
    
    # Champs techniques
    enabled = fields.Boolean(
        string='Activé',
        default=True,
        help='Indique si le VLAN est activé'
    )
    
    purpose = fields.Selection(
        selection=[
            ('corporate', 'Corporate'),
            ('guest', 'Guest'),
            ('iot', 'IoT'),
            ('management', 'Management'),
            ('voip', 'VoIP'),
            ('other', 'Autre')
        ],
        string='Usage',
        default='corporate',
        help='Usage prévu pour ce VLAN'
    )
    
    # Champs réseau
    subnet = fields.Char(
        string='Sous-réseau',
        help='Sous-réseau au format CIDR (ex: 192.168.1.0/24)'
    )
    
    network_id = fields.Many2one(
        comodel_name='unifi.network',
        string='Réseau associé',
        help='Réseau associé à ce VLAN'
    )
    
    # Champs de relation
    site_id = fields.Many2one(
        comodel_name='unifi.site',
        string='Site',
        required=True,
        ondelete='cascade',
        help='Site UniFi auquel ce VLAN appartient'
    )
    
    # Champs de synchronisation
    vlan_api_id = fields.Char(
        string='ID API',
        help='Identifiant unique du VLAN dans l\'API UniFi'
    )
    
    last_sync = fields.Datetime(
        string='Dernière synchronisation',
        help='Date et heure de la dernière synchronisation avec l\'API'
    )
    
    created_at = fields.Datetime(
        string='Créé le',
        help='Date et heure de création du VLAN dans UniFi'
    )
    
    updated_at = fields.Datetime(
        string='Mis à jour le',
        help='Date et heure de la dernière mise à jour du VLAN dans UniFi'
    )
    
    # Données brutes
    raw_data = fields.Text(
        string='Données brutes',
        help='Données brutes JSON du VLAN depuis l\'API'
    )
    
    _sql_constraints = [
        ('vlan_id_site_uniq', 'unique(vlan_id, site_id)', 'L\'ID VLAN doit être unique par site!')
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge de la méthode create pour ajouter des validations
        
        Args:
            vals_list (list): Liste des valeurs pour créer les enregistrements
            
        Returns:
            unifi.vlan: Les enregistrements créés
        """
        return super(UnifiVLAN, self).create(vals_list)
    
    def write(self, vals):
        """Surcharge de la méthode write pour ajouter des validations
        
        Args:
            vals (dict): Valeurs à écrire
            
        Returns:
            bool: Résultat de l'opération d'écriture
        """
        return super(UnifiVLAN, self).write(vals)
    
    @api.model
    def create_or_update_from_api(self, site, vlan_data):
        """Crée ou met à jour un VLAN à partir des données de l'API
        
        Cette méthode analyse les données de l'API et crée ou met à jour
        l'enregistrement VLAN correspondant.
        
        Args:
            site (unifi.site): L'enregistrement du site
            vlan_data (dict): Les données du VLAN depuis l'API
            
        Returns:
            unifi.vlan: L'enregistrement VLAN créé ou mis à jour
        """
        # Extraire l'ID API du VLAN
        vlan_api_id = vlan_data.get('_id') or vlan_data.get('id')
        
        if not vlan_api_id:
            _logger.warning("Données de VLAN sans ID API: %s", json.dumps(vlan_data))
            return False
        
        # Rechercher un VLAN existant avec cet ID API
        existing_vlan = self.search([
            ('vlan_api_id', '=', vlan_api_id),
            ('site_id', '=', site.id)
        ], limit=1)
        
        # Extraire les valeurs communes
        vlan_id = vlan_data.get('vlan_id') or vlan_data.get('id')
        if not vlan_id and isinstance(vlan_id, int):
            _logger.warning("Données de VLAN sans ID numérique: %s", json.dumps(vlan_data))
            return False
        
        # Préparer les valeurs pour la création ou mise à jour
        vals = {
            'vlan_api_id': vlan_api_id,
            'vlan_id': vlan_id,
            'name': vlan_data.get('name') or f"VLAN {vlan_id}",
            'purpose': vlan_data.get('purpose', 'corporate'),
            'enabled': vlan_data.get('enabled', True),
            'site_id': site.id,
            'raw_data': json.dumps(vlan_data),
            'last_sync': fields.Datetime.now()
        }
        
        # Ajouter les champs spécifiques s'ils existent
        if 'subnet' in vlan_data:
            vals['subnet'] = vlan_data['subnet']
        
        # Dates de création et mise à jour
        if 'created_at' in vlan_data:
            vals['created_at'] = fields.Datetime.from_string(vlan_data['created_at'])
        if 'updated_at' in vlan_data:
            vals['updated_at'] = fields.Datetime.from_string(vlan_data['updated_at'])
        
        if existing_vlan:
            # Mettre à jour le VLAN existant
            existing_vlan.write(vals)
            return existing_vlan
        else:
            # Créer un nouveau VLAN
            return self.create(vals)
    
    @api.model
    def sync_vlans_from_api(self, site):
        """Synchronise les VLANs depuis l'API UniFi
        
        Cette méthode récupère tous les VLANs depuis l'API et les crée ou met à jour
        dans la base de données.
        
        Args:
            site (unifi.site): L'enregistrement du site
            
        Returns:
            list: Liste des VLANs synchronisés
        """
        # Récupérer les données des VLANs depuis l'API
        vlan_data_list = site.get_vlan_data()
        
        if not vlan_data_list:
            _logger.warning("Aucune donnée de VLAN récupérée pour le site %s", site.name)
            return False
        
        synced_vlans = []
        
        # Créer ou mettre à jour chaque VLAN
        for vlan_data in vlan_data_list:
            vlan = self.create_or_update_from_api(site, vlan_data)
            if vlan:
                synced_vlans.append(vlan)
        
        return synced_vlans
