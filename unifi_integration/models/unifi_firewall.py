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
    
    source_type = fields.Selection(
        selection=[
            ('address', 'Adresse IP'),
            ('network', 'Réseau'),
            ('object', 'Objet'),
            ('any', 'N\'importe où')
        ],
        string='Type de source',
        compute='_compute_source_type',
        store=True,
        help='Type de la source (adresse IP, réseau ou objet)'
    )
    
    source = fields.Char(
        string='Source',
        help='Réseau source ou adresse IP au format CIDR'
    )
    
    formatted_source = fields.Char(
        string='Source formatée',
        compute='_compute_formatted_source',
        store=True,
        help='Affichage formaté de la source en fonction de son type'
    )
    
    destination_type = fields.Selection(
        selection=[
            ('address', 'Adresse IP'),
            ('network', 'Réseau'),
            ('object', 'Objet'),
            ('any', 'N\'importe où')
        ],
        string='Type de destination',
        compute='_compute_destination_type',
        store=True,
        help='Type de la destination (adresse IP, réseau ou objet)'
    )
    
    destination = fields.Char(
        string='Destination',
        help='Réseau de destination ou adresse IP au format CIDR'
    )
    
    formatted_destination = fields.Char(
        string='Destination formatée',
        compute='_compute_formatted_destination',
        store=True,
        help='Affichage formaté de la destination en fonction de son type'
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
    
    detailed_rule_type = fields.Selection(
        selection=[
            ('internet-in-ipv4', 'Internet-in (IPv4)'),
            ('internet-out-ipv4', 'Internet-out (IPv4)'),
            ('internet-local-ipv4', 'Internet-local (IPv4)'),
            ('lan-in-ipv4', 'LAN-in (IPv4)'),
            ('lan-out-ipv4', 'LAN-out (IPv4)'),
            ('lan-local-ipv4', 'LAN-local (IPv4)'),
            ('guest-in-ipv4', 'Guest-in (IPv4)'),
            ('guest-out-ipv4', 'Guest-out (IPv4)'),
            ('guest-local-ipv4', 'Guest-local (IPv4)'),
            ('internet-in-ipv6', 'Internet-in (IPv6)'),
            ('internet-out-ipv6', 'Internet-out (IPv6)'),
            ('internet-local-ipv6', 'Internet-local (IPv6)'),
            ('lan-in-ipv6', 'LAN-in (IPv6)'),
            ('lan-out-ipv6', 'LAN-out (IPv6)'),
            ('lan-local-ipv6', 'LAN-local (IPv6)'),
            ('guest-in-ipv6', 'Guest-in (IPv6)'),
            ('guest-out-ipv6', 'Guest-out (IPv6)'),
            ('guest-local-ipv6', 'Guest-local (IPv6)'),
            ('other', 'Autre')
        ],
        string='Type détaillé',
        compute='_compute_detailed_rule_type',
        store=True,
        help='Type détaillé de la règle de pare-feu (Internet-in, LAN-out, etc.)'
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
    
    raw_data_json = fields.Text(
        string='Données brutes (JSON)',
        compute='_compute_raw_data_json',
        help='Données brutes de la règle de pare-feu au format JSON'
    )
    
    @api.depends('raw_data')
    def _compute_raw_data_json(self):
        for record in self:
            if record.raw_data:
                try:
                    # Charger le JSON, puis le formater sans les accolades externes
                    data = json.loads(record.raw_data)
                    formatted_json = json.dumps(data, indent=4)
                    # Enlever la première et la dernière ligne (les accolades)
                    lines = formatted_json.split('\n')
                    if len(lines) > 2:  # S'assurer qu'il y a au moins 3 lignes
                        # Enlever la première et la dernière ligne et ajuster l'indentation
                        inner_content = '\n'.join(line[4:] for line in lines[1:-1])
                        record.raw_data_json = inner_content
                    else:
                        record.raw_data_json = formatted_json
                except ValueError:
                    record.raw_data_json = 'Invalid JSON'


    # Champs calculés
    rule_summary = fields.Char(
        string='Résumé de la règle',
        compute='_compute_rule_summary'
    )
    
    @api.depends('raw_data')
    def _compute_detailed_rule_type(self):
        """Détermine le type détaillé de la règle de pare-feu à partir des données brutes"""
        for record in self:
            if not record.raw_data:
                record.detailed_rule_type = 'other'
                continue
                
            try:
                rule_data = json.loads(record.raw_data)
                # Extraire les informations du type de règle
                rule_interface = rule_data.get('ruleset', '')
                direction = rule_data.get('direction', '')
                ip_version = 'ipv4' if rule_data.get('ipv6', False) is False else 'ipv6'
                
                # Construire le type détaillé
                if rule_interface and direction:
                    detailed_type = f"{rule_interface}-{direction}-{ip_version}"
                    if detailed_type in dict(self._fields['detailed_rule_type'].selection).keys():
                        record.detailed_rule_type = detailed_type
                    else:
                        record.detailed_rule_type = 'other'
                else:
                    record.detailed_rule_type = 'other'
            except (json.JSONDecodeError, AttributeError):
                record.detailed_rule_type = 'other'
    
    @api.depends('source', 'raw_data')
    def _compute_source_type(self):
        """Détermine le type de la source (adresse IP, réseau ou objet)"""
        for record in self:
            if not record.source:
                record.source_type = 'any'
                continue
                
            try:
                rule_data = json.loads(record.raw_data) if record.raw_data else {}
                src_type = rule_data.get('src_type', '')
                
                if src_type == 'network':
                    record.source_type = 'network'
                elif src_type == 'object':
                    record.source_type = 'object'
                elif record.source and '/' in record.source:
                    # Si contient un slash, c'est probablement un réseau CIDR
                    record.source_type = 'network'
                elif record.source:
                    # Sinon, c'est probablement une adresse IP
                    record.source_type = 'address'
                else:
                    record.source_type = 'any'
            except (json.JSONDecodeError, AttributeError):
                if record.source:
                    record.source_type = 'address'
                else:
                    record.source_type = 'any'
    
    @api.depends('destination', 'raw_data')
    def _compute_destination_type(self):
        """Détermine le type de la destination (adresse IP, réseau ou objet)"""
        for record in self:
            if not record.destination:
                record.destination_type = 'any'
                continue
                
            try:
                rule_data = json.loads(record.raw_data) if record.raw_data else {}
                dst_type = rule_data.get('dst_type', '')
                
                if dst_type == 'network':
                    record.destination_type = 'network'
                elif dst_type == 'object':
                    record.destination_type = 'object'
                elif record.destination and '/' in record.destination:
                    # Si contient un slash, c'est probablement un réseau CIDR
                    record.destination_type = 'network'
                elif record.destination:
                    # Sinon, c'est probablement une adresse IP
                    record.destination_type = 'address'
                else:
                    record.destination_type = 'any'
            except (json.JSONDecodeError, AttributeError):
                if record.destination:
                    record.destination_type = 'address'
                else:
                    record.destination_type = 'any'
    
    @api.depends('source', 'source_type', 'raw_data')
    def _compute_formatted_source(self):
        """Calcule l'affichage formaté de la source en fonction de son type"""
        for record in self:
            if record.source_type == 'any' or not record.source:
                record.formatted_source = "N'importe où"
            elif record.source_type == 'object':
                try:
                    rule_data = json.loads(record.raw_data) if record.raw_data else {}
                    object_name = rule_data.get('src_object_name', record.source)
                    record.formatted_source = f"Objet: {object_name}"
                except (json.JSONDecodeError, AttributeError):
                    record.formatted_source = record.source
            elif record.source_type == 'network':
                record.formatted_source = f"Réseau: {record.source}"
            else:
                record.formatted_source = f"IP: {record.source}"
    
    @api.depends('destination', 'destination_type', 'raw_data')
    def _compute_formatted_destination(self):
        """Calcule l'affichage formaté de la destination en fonction de son type"""
        for record in self:
            if record.destination_type == 'any' or not record.destination:
                record.formatted_destination = "N'importe où"
            elif record.destination_type == 'object':
                try:
                    rule_data = json.loads(record.raw_data) if record.raw_data else {}
                    object_name = rule_data.get('dst_object_name', record.destination)
                    record.formatted_destination = f"Objet: {object_name}"
                except (json.JSONDecodeError, AttributeError):
                    record.formatted_destination = record.destination
            elif record.destination_type == 'network':
                record.formatted_destination = f"Réseau: {record.destination}"
            else:
                record.formatted_destination = f"IP: {record.destination}"
    
    @api.depends('action', 'protocol', 'formatted_source', 'formatted_destination', 'src_port', 'dst_port')
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
            
            src_addr = record.formatted_source or "N'importe où"
            dst_addr = record.formatted_destination or "N'importe où"
            
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
