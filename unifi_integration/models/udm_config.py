# -*- coding: utf-8 -*-

# Ces importations fonctionneront dans un environnement Odoo, même si votre IDE les signale comme non trouvées
# pylint: disable=import-error
from odoo import models, fields, api, _
from odoo.exceptions import UserError
# pylint: enable=import-error
import logging
import json
from datetime import datetime
import random  # Pour générer des données de test/démonstration

_logger = logging.getLogger(__name__)

class UdmSite(models.Model):
    """Représente un site UniFi géré par un ou plusieurs UDM Pro"""
    _name = 'udm.site'
    _description = 'UDM Site'
    _order = 'name'
    
    name = fields.Char(string='Name', required=True)
    site_id = fields.Char(string='Site ID', help="Identifiant du site dans UniFi (généralement 'default' sauf si configuré autrement)", default='default')
    description = fields.Text(string='Description')
    address = fields.Text(string='Physical Address')
    active = fields.Boolean(string='Active', default=True)
    
    # Relations
    configuration_ids = fields.One2many('udm.configuration', 'site_id', string='Configurations')
    dashboard_ids = fields.One2many('udm.dashboard.metric', 'site_id', string='Dashboard Metrics')
    
    # Compteurs
    config_count = fields.Integer(compute='_compute_counts', string='Configuration Count')
    device_count = fields.Integer(compute='_compute_device_count', string='Total Devices')
    client_count = fields.Integer(compute='_compute_client_count', string='Connected Clients')
    
    @api.depends('configuration_ids')
    def _compute_counts(self):
        for record in self:
            record.config_count = len(record.configuration_ids)
    
    @api.depends('configuration_ids.device_ids')
    def _compute_device_count(self):
        for record in self:
            count = 0
            for config in record.configuration_ids:
                count += len(config.device_ids)
            record.device_count = count
    
    @api.depends('dashboard_ids')
    def _compute_client_count(self):
        for record in self:
            client_metric = record.dashboard_ids.filtered(lambda m: m.metric_type == 'clients_count')
            if client_metric and len(client_metric) > 0:
                record.client_count = int(client_metric[0].current_value)
            else:
                record.client_count = 0
    
    def action_view_configurations(self):
        self.ensure_one()
        return {
            'name': _('Configurations'),
            'view_mode': 'tree,form',
            'res_model': 'udm.configuration',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
        }
    
    def action_view_dashboard(self):
        self.ensure_one()
        return {
            'name': _('Site Dashboard'),
            'view_mode': 'dashboard,form',
            'res_model': 'udm.site',
            'res_id': self.id,
            'type': 'ir.actions.act_window',
        }
    
    def action_refresh_metrics(self):
        """Rafraîchit les métriques du tableau de bord pour ce site"""
        self.ensure_one()
        configs = self.configuration_ids.filtered(lambda c: c.active)
        if not configs:
            raise UserError(_('No active UDM Pro configuration found for this site'))
            
        # Dans une implémentation réelle, vous appelleriez l'API UDM Pro ici
        # Pour le moment, nous simulons les métriques
        self._generate_sample_metrics()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    
    def _generate_sample_metrics(self):
        """Génère des métriques de démonstration pour le tableau de bord"""
        # Supprimer les anciennes métriques
        self.dashboard_ids.unlink()
        
        # Types de métriques à générer
        metric_types = [
            'bandwidth_usage', 'cpu_usage', 'memory_usage', 'clients_count',
            'wan_status', 'threat_count', 'device_status'
        ]
        
        # Générer les nouvelles métriques
        metrics_vals = []
        now = fields.Datetime.now()
        
        for metric_type in metric_types:
            # Générer la valeur actuelle
            current_value = ''
            max_value = ''
            history = ''
            
            if metric_type == 'bandwidth_usage':
                current_value = str(random.uniform(5, 200))  # Mbps
                max_value = '1000'
                history = self._generate_history_data(50, 250, 24)
            elif metric_type in ['cpu_usage', 'memory_usage']:
                current_value = str(random.uniform(10, 90))  # Pourcentage
                max_value = '100'
                history = self._generate_history_data(10, 90, 24)
            elif metric_type == 'clients_count':
                current_value = str(random.randint(5, 50))
                max_value = '100'
                history = self._generate_history_data(5, 60, 24, integer=True)
            elif metric_type == 'threat_count':
                current_value = str(random.randint(0, 10))
                max_value = '100'
                history = self._generate_history_data(0, 15, 24, integer=True)
            elif metric_type == 'wan_status':
                current_value = random.choice(['up', 'up'])  # Principalement en ligne
                max_value = ''
                history = ''
            elif metric_type == 'device_status':
                total = random.randint(5, 20)
                offline = random.randint(0, 2)
                current_value = f"{total-offline}/{total}"
                max_value = str(total)
                history = ''
            
            metrics_vals.append({
                'site_id': self.id,
                'metric_type': metric_type,
                'current_value': current_value,
                'max_value': max_value,
                'history_data': history,
                'last_update': now,
            })
        
        # Créer les métriques
        for vals in metrics_vals:
            self.env['udm.dashboard.metric'].create(vals)
    
    def _generate_history_data(self, min_val, max_val, points, integer=False):
        """Génère des données historiques pour les graphiques"""
        data = []
        for _ in range(points):  # Utilisation de _ pour indiquer une variable non utilisée
            if integer:
                value = random.randint(min_val, max_val)
            else:
                value = random.uniform(min_val, max_val)
                value = round(value, 2)
            data.append(value)
        return json.dumps(data)


class UdmDashboardMetric(models.Model):
    """Stocke les métriques pour le tableau de bord UDM Pro"""
    _name = 'udm.dashboard.metric'
    _description = 'UDM Dashboard Metric'
    _order = 'last_update desc'
    
    site_id = fields.Many2one('udm.site', string='Site', required=True, ondelete='cascade')
    metric_type = fields.Selection([
        ('bandwidth_usage', 'Bandwidth Usage'),
        ('cpu_usage', 'CPU Usage'),
        ('memory_usage', 'Memory Usage'),
        ('clients_count', 'Connected Clients'),
        ('wan_status', 'WAN Status'),
        ('threat_count', 'Security Threats'),
        ('device_status', 'Device Status'),
    ], string='Metric Type', required=True)
    
    current_value = fields.Char(string='Current Value', required=True)
    max_value = fields.Char(string='Maximum Value')
    history_data = fields.Text(string='Historical Data', help="Données JSON pour les graphiques d'historique")
    last_update = fields.Datetime(string='Last Update', default=fields.Datetime.now)
    
    # Champs calculés pour l'affichage
    formatted_value = fields.Char(compute='_compute_formatted_value', string='Formatted Value')
    status = fields.Selection([
        ('normal', 'Normal'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ], compute='_compute_status', string='Status')
    
    @api.depends('current_value', 'metric_type')
    def _compute_formatted_value(self):
        for record in self:
            if record.metric_type == 'bandwidth_usage':
                try:
                    value = float(record.current_value)
                    if value >= 1000:
                        record.formatted_value = f"{value/1000:.2f} Gbps"
                    else:
                        record.formatted_value = f"{value:.2f} Mbps"
                except (ValueError, TypeError):
                    record.formatted_value = record.current_value
            elif record.metric_type in ['cpu_usage', 'memory_usage']:
                try:
                    value = float(record.current_value)
                    record.formatted_value = f"{value:.1f}%"
                except (ValueError, TypeError):
                    record.formatted_value = record.current_value
            elif record.metric_type == 'wan_status':
                if record.current_value == 'up':
                    record.formatted_value = _('Online')
                else:
                    record.formatted_value = _('Offline')
            else:
                record.formatted_value = record.current_value
    
    @api.depends('current_value', 'max_value', 'metric_type')
    def _compute_status(self):
        for record in self:
            if record.metric_type in ['cpu_usage', 'memory_usage']:
                try:
                    value = float(record.current_value)
                    if value > 90:
                        record.status = 'critical'
                    elif value > 70:
                        record.status = 'warning'
                    else:
                        record.status = 'normal'
                except (ValueError, TypeError):
                    record.status = 'normal'
            elif record.metric_type == 'bandwidth_usage':
                try:
                    value = float(record.current_value)
                    max_value = float(record.max_value) if record.max_value else 1000
                    if value > max_value * 0.9:
                        record.status = 'critical'
                    elif value > max_value * 0.7:
                        record.status = 'warning'
                    else:
                        record.status = 'normal'
                except (ValueError, TypeError):
                    record.status = 'normal'
            elif record.metric_type == 'threat_count':
                try:
                    value = int(record.current_value)
                    if value > 5:
                        record.status = 'critical'
                    elif value > 0:
                        record.status = 'warning'
                    else:
                        record.status = 'normal'
                except (ValueError, TypeError):
                    record.status = 'normal'
            elif record.metric_type == 'wan_status':
                if record.current_value == 'up':
                    record.status = 'normal'
                else:
                    record.status = 'critical'
            else:
                record.status = 'normal'


class UdmConfiguration(models.Model):
    """Configuration complète d'un UDM Pro stockée dans Odoo"""
    _name = 'udm.configuration'
    _description = 'UDM Pro Configuration'
    _order = 'timestamp desc'
    
    name = fields.Char(string='Name', compute='_compute_name', store=True)
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now, required=True)
    raw_data = fields.Text(string='Raw Data', help="Les données brutes de configuration en format JSON")
    active = fields.Boolean(string='Active', default=True, help="Indique si cette configuration est actuellement active")
    
    # Connexion à l'UDM Pro
    host = fields.Char(string='Host', help="Adresse IP ou nom d'hôte de l'UDM Pro")
    port = fields.Integer(string='Port', default=443)
    username = fields.Char(string='Username')
    password = fields.Char(string='Password')
    
    # Relations
    site_id = fields.Many2one('udm.site', string='Site', ondelete='restrict')
    system_info_id = fields.Many2one('udm.system.info', string='System Info', ondelete='cascade')
    network_ids = fields.One2many('udm.network', 'config_id', string='Networks')
    vlan_ids = fields.One2many('udm.vlan', 'config_id', string='VLANs')
    device_ids = fields.One2many('udm.device', 'config_id', string='Devices')
    user_ids = fields.One2many('udm.user', 'config_id', string='Users')
    settings_id = fields.Many2one('udm.settings', string='Settings', ondelete='cascade')
    firewall_rule_ids = fields.One2many('udm.firewall.rule', 'config_id', string='Firewall Rules')
    
    # Statistiques
    network_count = fields.Integer(compute='_compute_counts', string='Network Count')
    device_count = fields.Integer(compute='_compute_counts', string='Device Count')
    user_count = fields.Integer(compute='_compute_counts', string='User Count')
    firewall_rule_count = fields.Integer(compute='_compute_counts', string='Firewall Rule Count')
    
    @api.depends('timestamp', 'system_info_id.hostname')
    def _compute_name(self):
        for record in self:
            hostname = record.system_info_id.hostname or 'Unknown'
            timestamp = record.timestamp.strftime('%Y-%m-%d %H:%M:%S') if record.timestamp else ''
            record.name = f"{hostname} ({timestamp})"
    
    @api.depends('network_ids', 'device_ids', 'user_ids', 'firewall_rule_ids')
    def _compute_counts(self):
        for record in self:
            record.network_count = len(record.network_ids)
            record.device_count = len(record.device_ids)
            record.user_count = len(record.user_ids)
            record.firewall_rule_count = len(record.firewall_rule_ids)
    
    def action_view_networks(self):
        self.ensure_one()
        return {
            'name': _('Networks'),
            'view_mode': 'tree,form',
            'res_model': 'udm.network',
            'domain': [('config_id', '=', self.id)],
            'type': 'ir.actions.act_window',
        }
    
    def action_view_devices(self):
        self.ensure_one()
        return {
            'name': _('Devices'),
            'view_mode': 'tree,form',
            'res_model': 'udm.device',
            'domain': [('config_id', '=', self.id)],
            'type': 'ir.actions.act_window',
        }
    
    def action_view_users(self):
        self.ensure_one()
        return {
            'name': _('Users'),
            'view_mode': 'tree,form',
            'res_model': 'udm.user',
            'domain': [('config_id', '=', self.id)],
            'type': 'ir.actions.act_window',
        }
    
    def action_view_firewall_rules(self):
        self.ensure_one()
        return {
            'name': _('Firewall Rules'),
            'view_mode': 'tree,form',
            'res_model': 'udm.firewall.rule',
            'domain': [('config_id', '=', self.id)],
            'type': 'ir.actions.act_window',
        }
    
    @api.model
    def import_configuration(self, config_data):
        """
        Importe une configuration UDM Pro complète dans Odoo
        
        Args:
            config_data (dict): Données de configuration brutes de l'API
        
        Returns:
            int: ID de la configuration créée
        """
        if not config_data:
            raise UserError(_("No configuration data provided"))
        
        # Créer la configuration principale
        vals = {
            'timestamp': datetime.now(),
            'raw_data': json.dumps(config_data, indent=2, ensure_ascii=False),
        }
        
        config = self.create(vals)
        
        # Créer les informations système
        system_info_data = config_data.get('system_info', {})
        if system_info_data:
            system_info = self.env['udm.system.info'].create({
                'config_id': config.id,
                'hostname': system_info_data.get('hostname', ''),
                'version': system_info_data.get('version', ''),
                'model': system_info_data.get('model', ''),
                'uptime': system_info_data.get('uptime', 0),
                'serial': system_info_data.get('serialNumber', ''),
                'mac_address': system_info_data.get('macAddress', ''),
                'raw_data': json.dumps(system_info_data, indent=2, ensure_ascii=False),
            })
            config.system_info_id = system_info.id
        
        # Créer les réseaux
        networks_data = config_data.get('networks', {}).get('networks', [])
        for network_data in networks_data:
            if isinstance(network_data, dict):
                self.env['udm.network'].create({
                    'config_id': config.id,
                    'name': network_data.get('name', ''),
                    'purpose': network_data.get('purpose', ''),
                    'subnet': network_data.get('subnet', ''),
                    'vlan_id_number': network_data.get('vlanId'),
                    'dhcp_enabled': network_data.get('dhcpEnabled', False),
                    'dhcp_start': network_data.get('dhcpStart', ''),
                    'dhcp_stop': network_data.get('dhcpStop', ''),
                    'domain_name': network_data.get('domainName', ''),
                    'raw_data': json.dumps(network_data, indent=2, ensure_ascii=False),
                })
        
        # Créer les VLANs
        vlans_data = config_data.get('networks', {}).get('vlans', [])
        for vlan_data in vlans_data:
            if isinstance(vlan_data, dict):
                self.env['udm.vlan'].create({
                    'config_id': config.id,
                    'vlan_id': vlan_data.get('id', 0),
                    'name': vlan_data.get('name', ''),
                    'raw_data': json.dumps(vlan_data, indent=2, ensure_ascii=False),
                })
        
        # Créer les périphériques
        devices_data = config_data.get('devices', {}).get('devices', [])
        for device_data in devices_data:
            if isinstance(device_data, dict):
                self.env['udm.device'].create({
                    'config_id': config.id,
                    'name': device_data.get('name', ''),
                    'mac': device_data.get('mac', ''),
                    'ip': device_data.get('ip', ''),
                    'device_type': device_data.get('type', ''),
                    'model': device_data.get('model', ''),
                    'last_seen': datetime.fromtimestamp(device_data.get('lastSeen', 0)),
                    'raw_data': json.dumps(device_data, indent=2, ensure_ascii=False),
                })
        
        # Créer les utilisateurs
        users_data = config_data.get('users', {}).get('users', [])
        for user_data in users_data:
            if isinstance(user_data, dict):
                self.env['udm.user'].create({
                    'config_id': config.id,
                    'name': user_data.get('name', ''),
                    'email': user_data.get('email', ''),
                    'role': user_data.get('role', ''),
                    'enabled': user_data.get('enabled', True),
                    'raw_data': json.dumps(user_data, indent=2, ensure_ascii=False),
                })
        
        # Créer les paramètres
        settings_data = config_data.get('settings', {})
        if settings_data:
            settings = self.env['udm.settings'].create({
                'config_id': config.id,
                'timezone': settings_data.get('timezone', ''),
                'ntp_servers': ','.join(settings_data.get('ntpServers', [])),
                'dns_servers': ','.join(settings_data.get('dnsServers', [])),
                'raw_data': json.dumps(settings_data, indent=2, ensure_ascii=False),
            })
            config.settings_id = settings.id
        
        # Créer les règles de pare-feu
        firewall_data = config_data.get('firewall', {}).get('rules', [])
        for rule_data in firewall_data:
            if isinstance(rule_data, dict):
                self.env['udm.firewall.rule'].create({
                    'config_id': config.id,
                    'name': rule_data.get('name', ''),
                    'description': rule_data.get('description', ''),
                    'action': rule_data.get('action', 'drop'),
                    'protocol': rule_data.get('protocol', ''),
                    'source': rule_data.get('source', ''),
                    'destination': rule_data.get('destination', ''),
                    'enabled': rule_data.get('enabled', True),
                    'raw_data': json.dumps(rule_data, indent=2, ensure_ascii=False),
                })
        
        # Journaliser l'importation réussie
        _logger.info('Successfully imported UDM Pro configuration: %s', config.name)
        
        return config.id
    
    def action_compare_with(self):
        """Ouvre un assistant pour comparer cette configuration avec une autre"""
        self.ensure_one()
        return {
            'name': _('Compare Configurations'),
            'type': 'ir.actions.act_window',
            'res_model': 'udm.configuration.compare.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_source_config_id': self.id,
            },
        }
    
    def action_duplicate(self):
        """Duplique cette configuration"""
        self.ensure_one()
        
        # Créer une nouvelle configuration en copiant les données brutes
        new_config = self.copy({
            'timestamp': datetime.now(),
            'name': _('%s (Copy)') % self.name,
        })
        
        return {
            'name': _('Duplicated Configuration'),
            'type': 'ir.actions.act_window',
            'res_model': 'udm.configuration',
            'res_id': new_config.id,
            'view_mode': 'form',
        }
    
    def action_generate_report(self):
        """Génère un rapport PDF de cette configuration"""
        self.ensure_one()
        return self.env.ref('udm_pro_docs.action_report_udm_configuration').report_action(self)
        
    def action_view_dashboard(self):
        """Affiche le tableau de bord pour le site de cette configuration"""
        self.ensure_one()
        if not self.site_id:
            raise UserError(_('This configuration is not associated with any site. Please set a site first.'))
            
        return {
            'name': _('Site Dashboard'),
            'view_mode': 'dashboard,form',
            'res_model': 'udm.site',
            'res_id': self.site_id.id,
            'type': 'ir.actions.act_window',
        }
        
    def action_update_dashboard_metrics(self):
        """Met à jour les métriques du tableau de bord pour le site de cette configuration"""
        self.ensure_one()
        if not self.site_id:
            raise UserError(_('This configuration is not associated with any site. Please set a site first.'))
            
        # Appeler la méthode de rafraîchissement des métriques du site
        return self.site_id.action_refresh_metrics()
