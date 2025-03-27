# -*- coding: utf-8 -*-

import json
import logging

from odoo import models, fields, api
from .unifi_common import UnifiCommonMixin

_logger = logging.getLogger(__name__)

class UnifiPortForward(models.Model, UnifiCommonMixin):
    """Représente une règle de redirection de port dans le système UniFi
    
    Ce modèle stocke les règles de redirection de port qui permettent un accès externe
    aux services internes. Chaque règle associe un port externe à une adresse IP
    et un port internes.
    
    Les redirections de port sont liées à un site spécifique et sont automatiquement
    supprimées lorsque le site est supprimé (cascade).
    """
    _name = 'unifi.port.forward'
    _description = 'Redirection de port UniFi'
    _order = 'sequence, id'
    
    site_id = fields.Many2one(
        comodel_name='unifi.site', 
        string='Site', 
        required=True,
        ondelete='cascade',
        help='Site auquel appartient cette redirection de port'
    )
    
    name = fields.Char(
        string='Nom', 
        required=True,
        help='Nom de la règle'
    )
    
    description = fields.Text(
        string='Description',
        help='Description détaillée de l\'objectif de la redirection de port'
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
    
    protocol = fields.Selection(
        selection=[
            ('tcp', 'TCP'),
            ('udp', 'UDP'),
            ('tcp_udp', 'TCP & UDP')
        ],
        string='Protocole',
        required=True,
        default='tcp',
        help='Protocole réseau à rediriger'
    )
    
    source = fields.Char(
        string='Source',
        help='Réseau source ou adresse IP au format CIDR'
    )
    
    dst_port = fields.Char(
        string='Port de destination',
        required=True,
        help='Numéro de port externe ou plage (ex: 80 ou 1024-2048)'
    )
    
    fwd_ip = fields.Char(
        string='IP de redirection',
        required=True,
        help='Adresse IP interne vers laquelle rediriger'
    )
    
    fwd_port = fields.Char(
        string='Port de redirection',
        required=True,
        help='Numéro de port interne ou plage'
    )
    
    # Champs spécifiques à l'API
    rule_id = fields.Char(
        string='ID de la règle',
        help='Identifiant unique de la règle dans le système UniFi'
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
        help='Données brutes de la redirection de port au format JSON'
    )
    
    raw_data_json = fields.Text(
        string='Données brutes (JSON)',
        compute='_compute_raw_data_json',
        help='Données brutes de la redirection de port au format JSON formaté'
    )
    
    @api.depends('raw_data')
    def _compute_raw_data_json(self):
        for record in self:
            record.raw_data_json = self.format_raw_data_json(record.raw_data)
    
    # Champs calculés
    rule_summary = fields.Char(
        string='Résumé de la règle',
        compute='_compute_rule_summary'
    )
    
    @api.depends('protocol', 'source', 'dst_port', 'fwd_ip', 'fwd_port')
    def _compute_rule_summary(self):
        """Calcule un résumé lisible de la règle de redirection de port
        
        Cette méthode génère une description concise du protocole de la règle,
        de la source et des mappages de ports. Le résumé est utilisé dans les
        vues de liste et les rapports pour comprendre rapidement ce que fait
        la règle sans afficher tous les détails.
        
        Exemples de résumés:
        - TCP de n'importe où:80 vers 192.168.1.100:8080
        - UDP de 203.0.113.0/24:53 vers 192.168.2.10:53
        - TCP & UDP de n'importe où:25565 vers 192.168.3.50:25565
        """
        for record in self:
            parts = []
            
            if record.protocol:
                parts.append(record.protocol.upper())
            
            src = f"de {record.source or 'n\'importe où'}"
            if record.dst_port:
                src += f":{record.dst_port}"
            parts.append(src)
            
            dst = f"vers {record.fwd_ip}"
            if record.fwd_port:
                dst += f":{record.fwd_port}"
            parts.append(dst)
            
            record.rule_summary = ' '.join(parts)
    
    @api.model
    def create_or_update_from_data(self, site, rule_data):
        """Crée ou met à jour une redirection de port à partir des données de l'API
        
        Cette méthode prend les données brutes d'une redirection de port provenant de l'API UniFi
        et crée ou met à jour l'enregistrement correspondant dans Odoo.
        
        Args:
            site: L'enregistrement du site UniFi
            rule_data: Les données de la redirection de port provenant de l'API
            
        Returns:
            record: L'enregistrement de la redirection de port créé ou mis à jour
        """
        # Extraire l'ID de la règle
        rule_id = rule_data.get('_id')
        
        if not rule_id:
            _logger.warning("Données de redirection de port sans ID: %s", json.dumps(rule_data))
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
            'protocol': rule_data.get('proto', 'tcp'),
            'source': rule_data.get('src', ''),
            'dst_port': rule_data.get('dst_port', ''),
            'fwd_ip': rule_data.get('fwd', ''),
            'fwd_port': rule_data.get('fwd_port', ''),
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
    def sync_port_forwards(self, site):
        """Synchronise les redirections de port depuis l'API UniFi
        
        Cette méthode récupère toutes les redirections de port depuis l'API UniFi
        et les synchronise avec les enregistrements dans Odoo.
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            bool: True si la synchronisation a réussi, False sinon
        """
        # Récupérer les données des redirections de port depuis l'API
        rule_data = site.get_port_forward_data()
        
        if not rule_data:
            _logger.warning("Aucune donnée de redirection de port récupérée pour le site %s", site.name)
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
            _logger.info("Suppression de %s redirections de port orphelines pour le site %s", 
                         len(orphaned_rules), site.name)
            orphaned_rules.unlink()
        
        return True
