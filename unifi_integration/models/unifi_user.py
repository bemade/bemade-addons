# -*- coding: utf-8 -*-

# These imports will work in an Odoo environment, even if your IDE marks them as not found
# pylint: disable=import-error
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
# pylint: enable=import-error

import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class UnifiUser(models.Model):
    """Modèle pour gérer les utilisateurs UniFi
    
    Ce modèle représente les utilisateurs configurés dans les sites UniFi,
    qu'ils soient gérés par l'API Controller ou l'API Site Manager.
    """
    _name = 'unifi.user'
    _description = 'Utilisateur UniFi'
    _order = 'name'
    
    # Champs d'identification
    name = fields.Char(
        string='Nom',
        required=True,
        help='Nom de l\'utilisateur'
    )
    
    user_id = fields.Char(
        string='ID Utilisateur',
        required=True,
        help='Identifiant unique de l\'utilisateur dans le système UniFi'
    )
    
    # Champs de configuration utilisateur
    mac = fields.Char(
        string='Adresse MAC',
        help='Adresse MAC de l\'appareil de l\'utilisateur'
    )
    
    email = fields.Char(
        string='Email',
        help='Adresse email de l\'utilisateur'
    )
    
    note = fields.Text(
        string='Note',
        help='Note ou commentaire sur l\'utilisateur'
    )
    
    is_connected = fields.Boolean(
        string='Connecté',
        default=False,
        help='Indique si l\'utilisateur est actuellement connecté au réseau'
    )
    
    is_guest = fields.Boolean(
        string='Invité',
        default=False,
        help='Indique si l\'utilisateur est un invité'
    )
    
    user_group_id = fields.Char(
        string='ID Groupe',
        help='Identifiant du groupe d\'utilisateurs'
    )
    
    blocked = fields.Boolean(
        string='Bloqué',
        default=False,
        help='Indique si l\'utilisateur est bloqué'
    )
    
    # Champs pour la gestion des invités
    authorized_at = fields.Datetime(
        string='Autorisé le',
        help='Date à laquelle l\'utilisateur a été autorisé'
    )
    
    expires_at = fields.Datetime(
        string='Expire le',
        help='Date d\'expiration de l\'autorisation de l\'utilisateur'
    )
    
    # Champs pour le suivi et l'audit
    created_at = fields.Datetime(
        string='Créé le',
        default=fields.Datetime.now,
        help='Date de création de l\'utilisateur dans Odoo'
    )
    
    updated_at = fields.Datetime(
        string='Mis à jour le',
        help='Date de dernière mise à jour de l\'utilisateur dans Odoo'
    )
    
    last_sync = fields.Datetime(
        string='Dernière synchronisation',
        help='Date de la dernière synchronisation avec l\'API UniFi'
    )
    
    last_seen = fields.Datetime(
        string='Dernière connexion',
        help='Date de la dernière connexion de l\'utilisateur au réseau'
    )
    
    # Stockage des données brutes
    raw_data = fields.Text(
        string='Données brutes',
        help='Données brutes de l\'utilisateur au format JSON'
    )
    
    # Relations
    site_id = fields.Many2one(
        comodel_name='unifi.site',
        string='Site',
        required=True,
        ondelete='cascade',
        help='Site UniFi auquel appartient cet utilisateur'
    )
    
    # Champs calculés
    status = fields.Selection(
        selection=[
            ('active', 'Actif'),
            ('inactive', 'Inactif'),
            ('guest', 'Invité'),
            ('blocked', 'Bloqué'),
            ('expired', 'Expiré')
        ],
        string='Statut',
        compute='_compute_status',
        store=True,
        help='Statut actuel de l\'utilisateur'
    )
    
    @api.depends('blocked', 'is_guest', 'expires_at', 'last_seen')
    def _compute_status(self):
        """Calcule le statut de l'utilisateur en fonction de ses attributs"""
        for user in self:
            if user.blocked:
                user.status = 'blocked'
            elif user.is_guest:
                if user.expires_at and user.expires_at < fields.Datetime.now():
                    user.status = 'expired'
                else:
                    user.status = 'guest'
            elif user.last_seen:
                # Considérer comme actif s'il a été vu dans les dernières 24h
                time_diff = fields.Datetime.now() - user.last_seen
                if time_diff.total_seconds() < 86400:  # 24 heures en secondes
                    user.status = 'active'
                else:
                    user.status = 'inactive'
            else:
                user.status = 'inactive'
    
    def create_or_update_from_data(self, site, user_data):
        """Crée ou met à jour un utilisateur à partir des données de l'API
        
        Args:
            site: L'enregistrement du site UniFi
            user_data: Les données de l'utilisateur depuis l'API
            
        Returns:
            record: L'enregistrement de l'utilisateur créé ou mis à jour
        """
        # Extraction de l'identifiant de l'utilisateur
        user_id = user_data.get('_id') or user_data.get('id')
        if not user_id:
            _logger.error("Impossible de créer/mettre à jour l'utilisateur: identifiant manquant")
            return False
        
        # Recherche d'un utilisateur existant avec cet identifiant
        existing_user = self.search([
            ('user_id', '=', user_id),
            ('site_id', '=', site.id)
        ], limit=1)
        
        # Préparation des valeurs pour la création/mise à jour
        vals = {
            'user_id': user_id,
            'name': user_data.get('name', user_data.get('hostname', f"Utilisateur {user_id}")),
            'site_id': site.id,
            'mac': user_data.get('mac'),
            'email': user_data.get('email'),
            'note': user_data.get('note', user_data.get('usergroup_id')),
            'is_guest': user_data.get('is_guest', False),
            'user_group_id': user_data.get('usergroup_id'),
            'blocked': user_data.get('blocked', False),
            'last_sync': fields.Datetime.now(),
            'raw_data': json.dumps(user_data)
        }
        
        # Traitement des dates
        if 'authorized_at' in user_data and user_data['authorized_at']:
            try:
                vals['authorized_at'] = datetime.fromtimestamp(user_data['authorized_at'] / 1000)
            except (ValueError, TypeError):
                _logger.warning(f"Format de date invalide pour authorized_at: {user_data['authorized_at']}")
        
        if 'expires_at' in user_data and user_data['expires_at']:
            try:
                vals['expires_at'] = datetime.fromtimestamp(user_data['expires_at'] / 1000)
            except (ValueError, TypeError):
                _logger.warning(f"Format de date invalide pour expires_at: {user_data['expires_at']}")
        
        if 'last_seen' in user_data and user_data['last_seen']:
            try:
                vals['last_seen'] = datetime.fromtimestamp(user_data['last_seen'] / 1000)
            except (ValueError, TypeError):
                _logger.warning(f"Format de date invalide pour last_seen: {user_data['last_seen']}")
        
        if existing_user:
            # Mise à jour de l'utilisateur existant
            vals['updated_at'] = fields.Datetime.now()
            existing_user.write(vals)
            return existing_user
        else:
            # Création d'un nouvel utilisateur
            return self.create(vals)
    
    def sync_users(self, site):
        """Synchronise les utilisateurs depuis l'API UniFi
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            bool: True si la synchronisation a réussi, False sinon
        """
        self.ensure_one()
        
        # Déterminer quelle méthode utiliser en fonction du type d'API
        if site.api_type == 'controller':
            return self._sync_users_controller(site)
        elif site.api_type == 'site_manager':
            return self._sync_users_site_manager(site)
        else:
            _logger.error(f"Type d'API non pris en charge: {site.api_type}")
            return False
    
    def _sync_users_controller(self, site):
        """Synchronise les utilisateurs depuis l'API Controller
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            bool: True si la synchronisation a réussi, False sinon
        """
        # Obtenir les données des utilisateurs depuis l'API Controller
        users_data = self.env['unifi.site.controller'].get_user_data(site)
        if not users_data:
            return False
        
        # Créer ou mettre à jour les utilisateurs
        for user_data in users_data:
            self.create_or_update_from_data(site, user_data)
        
        return True
    
    def _sync_users_site_manager(self, site):
        """Synchronise les utilisateurs depuis l'API Site Manager
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            bool: True si la synchronisation a réussi, False sinon
        """
        # Obtenir les données des utilisateurs depuis l'API Site Manager
        users_data = self.env['unifi.site.manager'].get_user_data(site)
        if not users_data:
            return False
        
        # Créer ou mettre à jour les utilisateurs
        for user_data in users_data:
            self.create_or_update_from_data(site, user_data)
        
        return True
