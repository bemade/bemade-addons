# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

class UnifiFirewallRule(models.Model):
    """Représente une règle de pare-feu dans le système UniFi
    
    Ce modèle stocke les règles de pare-feu qui contrôlent le trafic réseau. Chaque règle
    spécifie quel trafic est autorisé ou bloqué en fonction de divers critères tels que
    les adresses source/destination, les ports et les protocoles.
    
    Les règles sont liées à un site spécifique et sont automatiquement supprimées lorsque
    le site est supprimé (cascade).
    """
    _name = 'unifi.firewall.rule'
    _description = 'Règle de pare-feu UniFi'
    _order = 'sequence, id'
    
    site_id = fields.Many2one(
        comodel_name='unifi.site', 
        string='Site', 
        required=True,
        ondelete='cascade',
        help='Site auquel appartient cette règle de pare-feu'
    )

    name = fields.Char(
        string='Nom', 
        required=True,
        help='Nom de la règle'
    )

    description = fields.Text(
        string='Description',
        help='Description détaillée de l\'objectif de la règle'
    )
    
    enabled = fields.Boolean(
        string='Activée', 
        default=True,
        help='Indique si cette règle est active'
    )
    
    sequence = fields.Integer(
        string='Séquence', 
        default=10,
        help='Ordre dans lequel les règles sont évaluées'
    )

    action = fields.Selection(
        selection=[
            ('accept', 'Accepter'),
            ('drop', 'Rejeter silencieusement'),
            ('reject', 'Rejeter avec notification')
        ],
        string='Action',
        required=True,
        default='drop',
        help='Action à effectuer lorsque la règle correspond'
    )
    
    protocol = fields.Selection(
        selection=[
            ('tcp', 'TCP'),
            ('udp', 'UDP'),
            ('icmp', 'ICMP'),
            ('all', 'Tous')
        ],
        string='Protocole',
        required=True,
        default='all',
        help='Protocole réseau auquel cette règle s\'applique'
    )
    
    source = fields.Char(
        string='Source',
        help='Réseau source ou adresse IP au format CIDR'
    )
    
    destination = fields.Char(
        string='Destination',
        help='Réseau de destination ou adresse IP au format CIDR'
    )
    
    src_port = fields.Char(
        string='Port source',
        help='Numéro de port source ou plage (ex: 80 ou 1024-2048)'
    )
    
    dst_port = fields.Char(
        string='Port de destination',
        help='Numéro de port de destination ou plage (ex: 80 ou 1024-2048)'
    )
    
    # Champs spécifiques à l'API
    rule_id = fields.Char(
        string='ID de la règle',
        help='Identifiant unique de la règle dans le système UniFi'
    )
    
    rule_type = fields.Selection(
        selection=[
            ('default', 'Défaut'),
            ('user', 'Utilisateur'),
            ('system', 'Système')
        ],
        string='Type de règle',
        default='user',
        help='Type de règle dans le système UniFi'
    )
    
    rule_index = fields.Integer(
        string='Index de la règle',
        help='Position de la règle dans la liste des règles'
    )
    
    # Champs d'audit
    created_at = fields.Datetime(
        string='Créé le',
        readonly=True,
        help='Date et heure de création de la règle'
    )
    
    updated_at = fields.Datetime(
        string='Mis à jour le',
        readonly=True,
        help='Date et heure de la dernière mise à jour de la règle'
    )
    
    last_sync = fields.Datetime(
        string='Dernière synchronisation',
        readonly=True,
        help='Date et heure de la dernière synchronisation avec l\'API UniFi'
    )
    
    raw_data = fields.Text(
        string='Données brutes',
        help='Données brutes de la règle de pare-feu au format JSON'
    )
    
    # Champs calculés
    rule_summary = fields.Char(
        string='Résumé de la règle',
        compute='_compute_rule_summary'
    )
    
    @api.depends('action', 'protocol', 'source', 'destination', 'src_port', 'dst_port')
    def _compute_rule_summary(self):
        """Calcule un résumé lisible de la règle de pare-feu
        
        Cette méthode génère une description concise de l'action de la règle,
        du protocole et des adresses et ports source/destination. Le résumé
        est utilisé dans les vues de liste et les rapports pour comprendre rapidement
        ce que fait la règle sans afficher tous les détails.
        
        Exemples de résumés:
        - ACCEPT TCP de 192.168.1.0/24:80 vers 10.0.0.0/8:443
        - DROP ICMP de 172.16.0.0/16 vers n'importe où
        - REJECT UDP de n'importe où vers 192.168.2.10:53
        """
        for record in self:
            parts = []
            
            if record.action:
                parts.append(record.action.upper())
            
            if record.protocol:
                parts.append(record.protocol.upper())
            
            src_addr = record.source or 'n\'importe où'
            dst_addr = record.destination or 'n\'importe où'
            
            src = f"de {src_addr}"
            if record.src_port:
                src += f":{record.src_port}"
            parts.append(src)
            
            dst = f"vers {dst_addr}"
            if record.dst_port:
                dst += f":{record.dst_port}"
            parts.append(dst)
            
            record.rule_summary = ' '.join(parts)
    
    @api.model
    def create_or_update_from_data(self, site, rule_data):
        """Crée ou met à jour une règle de pare-feu à partir des données de l'API
        
        Cette méthode prend les données brutes d'une règle de pare-feu provenant de l'API UniFi
        et crée ou met à jour l'enregistrement correspondant dans Odoo.
        
        Args:
            site: L'enregistrement du site UniFi
            rule_data: Les données de la règle de pare-feu provenant de l'API
            
        Returns:
            record: L'enregistrement de la règle de pare-feu créé ou mis à jour
        """
        # Extraire l'ID de la règle
        rule_id = rule_data.get('_id')
        
        if not rule_id:
            _logger.warning("Données de règle de pare-feu sans ID: %s", json.dumps(rule_data))
            return False
        
        # Rechercher une règle existante avec cet ID
        existing_rule = self.search([
            ('site_id', '=', site.id),
            ('rule_id', '=', rule_id)
        ], limit=1)
        
        # Préparer les valeurs pour la création ou la mise à jour
        values = {
            'site_id': site.id,
            'rule_id': rule_id,
            'name': rule_data.get('name', 'Sans nom'),
            'description': rule_data.get('description', ''),
            'enabled': rule_data.get('enabled', True),
            'sequence': rule_data.get('rule_index', 10),
            'rule_index': rule_data.get('rule_index', 0),
            'action': rule_data.get('action', 'drop'),
            'protocol': rule_data.get('protocol', 'all'),
            'source': rule_data.get('src', ''),
            'destination': rule_data.get('dst', ''),
            'src_port': rule_data.get('src_port', ''),
            'dst_port': rule_data.get('dst_port', ''),
            'rule_type': rule_data.get('rule_type', 'user'),
            'raw_data': json.dumps(rule_data),
            'last_sync': fields.Datetime.now()
        }
        
        # Si la règle existe, la mettre à jour
        if existing_rule:
            values['updated_at'] = fields.Datetime.now()
            existing_rule.write(values)
            return existing_rule
        
        # Sinon, créer une nouvelle règle
        values['created_at'] = fields.Datetime.now()
        return self.create(values)
    
    @api.model
    def sync_firewall_rules(self, site):
        """Synchronise les règles de pare-feu depuis l'API UniFi
        
        Cette méthode récupère toutes les règles de pare-feu depuis l'API UniFi
        et les synchronise avec les enregistrements dans Odoo.
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            bool: True si la synchronisation a réussi, False sinon
        """
        # Récupérer les données des règles de pare-feu depuis l'API
        rule_data = site.get_firewall_data()
        
        if not rule_data:
            _logger.warning("Aucune donnée de règle de pare-feu récupérée pour le site %s", site.name)
            return False
        
        # Garder une trace des règles synchronisées
        synced_rule_ids = []
        
        # Créer ou mettre à jour chaque règle
        for rule in rule_data:
            rule_record = self.create_or_update_from_data(site, rule)
            if rule_record:
                synced_rule_ids.append(rule_record.id)
        
        # Rechercher les règles qui n'existent plus dans l'API
        orphaned_rules = self.search([
            ('site_id', '=', site.id),
            ('id', 'not in', synced_rule_ids)
        ])
        
        # Supprimer les règles orphelines
        if orphaned_rules:
            _logger.info("Suppression de %s règles de pare-feu orphelines pour le site %s", 
                         len(orphaned_rules), site.name)
            orphaned_rules.unlink()
        
        return True
