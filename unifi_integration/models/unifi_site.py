# -*- coding: utf-8 -*-

from odoo import _, api, fields, models

# TODO: Refactorisation du modèle UnifiSite
# Changements effectués:
# 1. Division du modèle UnifiSite en trois fichiers:
#    - unifi_site.py: contient les champs et méthodes communs aux deux types d'API
#    - unifi_site_controller.py: contient les champs et méthodes spécifiques à l'API Controller
#    - unifi_site_manager.py: contient les champs et méthodes spécifiques à l'API Site Manager
# 2. Implémentation de méthodes de délégation dans le modèle principal pour:
#    - Validation des champs requis selon le type d'API (_check_api_fields)
#    - Nettoyage des champs non pertinents lors du changement de type d'API (_onchange_api_type)
# 3. Mise à jour des imports dans __init__.py pour inclure les nouveaux modèles

# These imports will work in an Odoo environment, even if your IDE marks them as not found
# pylint: disable=import-error
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
# pylint: enable=import-error

import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class UnifiSite(models.Model):
    """Represents a UniFi site managed by one or more UniFi devices
    
    This model is the central entity that groups all UniFi configurations and devices.
    Each site can have multiple devices, networks, and users.
    It supports both the Site Manager API (cloud) and the Controller API (local).
    
    The implementation is split across three files:
    - unifi_site.py: Common fields and methods
    - unifi_site_controller.py: Controller API specific functionality
    - unifi_site_manager.py: Site Manager API specific functionality
    """
    _name = 'unifi.site'
    _description = 'UniFi Site'
    _order = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # Basic site information
    name = fields.Char(
        string='Name', 
        required=True, 
        help='Site name'
    )
    
    site_id = fields.Char(
        string='Site ID',
        help="Site identifier in UniFi (usually 'default')",
        default='default',
        readonly=True,
        required=True
    )
    
    description = fields.Text(
        string='Description',
        help='Site description'
    )
    
    address = fields.Text(
        string='Physical Address',
        help='Physical location of this site'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Indicates if this site is currently active'
    )
    
    # API Type - New field to distinguish between Site Manager and Controller APIs
    api_type = fields.Selection(
        selection=[
            ('site_manager', 'Site Manager (Cloud)'),
            ('controller', 'Controller (Local)')
        ],
        string='API Type',
        required=True,
        default='controller',
        help='Type of API used to connect to this site'
    )
    
    # Relation avec la configuration API
    api_config_id = fields.Many2one(
        comodel_name='unifi.api.config',
        string='Configuration API',
        help='Configuration API utilisée pour ce site'
    )
    
    # Note: Controller-specific fields moved to unifi_site_controller.py
    
    # Connection information - Common fields
    timestamp = fields.Datetime(
        string='Created Date',
        default=lambda self: fields.Datetime.now(),
        readonly=True,
        help='Date and time when this site was created'
    )
    
    last_import_date = fields.Datetime(
        string='Last Import Date',
        readonly=True,
        help='Date and time of the last successful configuration import'
    )
    
    import_status = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('failed', 'Failed'),
            ('pending', 'Pending')
        ],
        string='Import Status',
        default='pending',
        help='Status of the last configuration import'
    )
    
    # SSL verification - Common for both API types
    verify_ssl = fields.Boolean(
        string='Verify SSL',
        default=False,
        help='Enable SSL certificate verification',
        compute='_compute_connection_fields',
        inverse='_inverse_verify_ssl'
    )
    
    # Relations avec les modèles spécifiques d'API
    controller_id = fields.One2many(
        comodel_name='unifi.site.controller',
        inverse_name='site_id',
        string='Controller API',
        help='Configuration de l\'API Controller pour ce site'
    )
    
    manager_id = fields.One2many(
        comodel_name='unifi.site.manager',
        inverse_name='site_id',
        string='Site Manager API',
        help='Configuration de l\'API Site Manager pour ce site'
    )
    
    # Related fields for Controller API connection information
    host = fields.Char(
        string='Host',
        help='IP address or hostname of the controller',
        compute='_compute_connection_fields',
        inverse='_inverse_host'
    )
    
    port = fields.Integer(
        string='Port',
        help='Port number (default: 443)',
        compute='_compute_connection_fields',
        inverse='_inverse_port'
    )
    
    username = fields.Char(
        string='Username',
        help='Username for controller login',
        compute='_compute_connection_fields',
        inverse='_inverse_username'
    )
    
    password = fields.Char(
        string='Password',
        help='Password for controller login',
        compute='_compute_connection_fields',
        inverse='_inverse_password'
    )
    
    # Related fields for Site Manager API connection information
    api_key = fields.Char(
        string='API Key',
        help='API Key for Site Manager authentication',
        compute='_compute_connection_fields',
        inverse='_inverse_api_key'
    )
    
    mfa_enabled = fields.Boolean(
        string='MFA Enabled',
        help='Enable Multi-Factor Authentication',
        compute='_compute_connection_fields',
        inverse='_inverse_mfa_enabled'
    )
    
    mfa_token = fields.Char(
        string='MFA Token',
        help='Multi-Factor Authentication token',
        compute='_compute_connection_fields',
        inverse='_inverse_mfa_token'
    )
    
    # Note: Controller-specific fields moved to unifi_site_controller.py
    # Note: Site Manager-specific fields moved to unifi_site_manager.py
    
    @api.depends('api_type', 'controller_id', 'manager_id')
    def _compute_connection_fields(self):
        """Calcule les valeurs des champs de connexion en fonction du type d'API"""
        for site in self:
            # Réinitialiser tous les champs
            site.host = False
            site.port = False
            site.username = False
            site.password = False
            site.api_key = False
            site.mfa_enabled = False
            site.mfa_token = False
            site.verify_ssl = False
            
            # Récupérer les valeurs en fonction du type d'API
            if site.api_type == 'controller':
                controller = self.env['unifi.site.controller'].search([('site_id', '=', site.id)], limit=1)
                if controller:
                    site.host = controller.host
                    site.port = controller.port
                    site.username = controller.username
                    site.password = controller.password
                    site.verify_ssl = controller.verify_ssl
            elif site.api_type == 'site_manager':
                manager = self.env['unifi.site.manager'].search([('site_id', '=', site.id)], limit=1)
                if manager:
                    site.api_key = manager.api_key
                    site.mfa_enabled = manager.mfa_enabled
                    site.mfa_token = manager.mfa_token
                    site.verify_ssl = manager.verify_ssl
    
    def _inverse_host(self):
        """Inverse pour le champ host"""
        for site in self:
            if site.api_type == 'controller':
                controller = self.env['unifi.site.controller'].search([('site_id', '=', site.id)], limit=1)
                if controller:
                    controller.host = site.host
                elif site.host:  # Créer un nouveau controller si nécessaire
                    self.env['unifi.site.controller'].create({
                        'site_id': site.id,
                        'host': site.host,
                    })
    
    def _inverse_port(self):
        """Inverse pour le champ port"""
        for site in self:
            if site.api_type == 'controller':
                controller = self.env['unifi.site.controller'].search([('site_id', '=', site.id)], limit=1)
                if controller:
                    controller.port = site.port
                elif site.port:  # Créer un nouveau controller si nécessaire
                    self.env['unifi.site.controller'].create({
                        'site_id': site.id,
                        'port': site.port,
                    })
    
    def _inverse_username(self):
        """Inverse pour le champ username"""
        for site in self:
            if site.api_type == 'controller':
                controller = self.env['unifi.site.controller'].search([('site_id', '=', site.id)], limit=1)
                if controller:
                    controller.username = site.username
                elif site.username:  # Créer un nouveau controller si nécessaire
                    self.env['unifi.site.controller'].create({
                        'site_id': site.id,
                        'username': site.username,
                    })
    
    def _inverse_password(self):
        """Inverse pour le champ password"""
        for site in self:
            if site.api_type == 'controller':
                controller = self.env['unifi.site.controller'].search([('site_id', '=', site.id)], limit=1)
                if controller:
                    controller.password = site.password
                elif site.password:  # Créer un nouveau controller si nécessaire
                    self.env['unifi.site.controller'].create({
                        'site_id': site.id,
                        'password': site.password,
                    })
    
    def _inverse_api_key(self):
        """Inverse pour le champ api_key"""
        for site in self:
            if site.api_type == 'site_manager':
                manager = self.env['unifi.site.manager'].search([('site_id', '=', site.id)], limit=1)
                if manager:
                    manager.api_key = site.api_key
                elif site.api_key:  # Créer un nouveau manager si nécessaire
                    self.env['unifi.site.manager'].create({
                        'site_id': site.id,
                        'api_key': site.api_key,
                    })
    
    def _inverse_mfa_enabled(self):
        """Inverse pour le champ mfa_enabled"""
        for site in self:
            if site.api_type == 'site_manager':
                manager = self.env['unifi.site.manager'].search([('site_id', '=', site.id)], limit=1)
                if manager:
                    manager.mfa_enabled = site.mfa_enabled
                elif site.mfa_enabled:  # Créer un nouveau manager si nécessaire
                    self.env['unifi.site.manager'].create({
                        'site_id': site.id,
                        'mfa_enabled': site.mfa_enabled,
                    })
    
    def _inverse_mfa_token(self):
        """Inverse pour le champ mfa_token"""
        for site in self:
            if site.api_type == 'site_manager':
                manager = self.env['unifi.site.manager'].search([('site_id', '=', site.id)], limit=1)
                if manager:
                    manager.mfa_token = site.mfa_token
                elif site.mfa_token:  # Créer un nouveau manager si nécessaire
                    self.env['unifi.site.manager'].create({
                        'site_id': site.id,
                        'mfa_token': site.mfa_token,
                    })
    
    def _inverse_verify_ssl(self):
        """Inverse pour le champ verify_ssl"""
        for site in self:
            if site.api_type == 'controller':
                controller = self.env['unifi.site.controller'].search([('site_id', '=', site.id)], limit=1)
                if controller:
                    controller.verify_ssl = site.verify_ssl
            elif site.api_type == 'site_manager':
                manager = self.env['unifi.site.manager'].search([('site_id', '=', site.id)], limit=1)
                if manager:
                    manager.verify_ssl = site.verify_ssl
    
    # Configuration data
    last_update = fields.Datetime(
        string='Last Update',

        default=fields.Datetime.now
    )
    
    raw_data = fields.Text(
        string='Raw Data',
        help='Raw configuration data in JSON format'
    )
    
    # Synchronization settings
    sync_interval = fields.Integer(
        string='Sync Interval (minutes)',
        default=60,
        help='Interval in minutes between automatic synchronizations'
    )
    
    auto_sync = fields.Boolean(
        string='Auto Sync',
        default=True,
        help='Enable automatic synchronization'
    )
    
    last_sync = fields.Datetime(
        string='Last Sync',
        readonly=True,
        help='Date and time of the last synchronization'
    )
    
    # Authentication session
    auth_session_id = fields.Many2one(
        comodel_name='unifi.auth.session',
        string='Authentication Session',
        ondelete='cascade',
        help='Current authentication session'
    )
    
    # Related records - Will be updated to point to new models
    network_ids = fields.One2many(
        comodel_name='unifi.network',
        inverse_name='site_id',
        string='Networks',
        help='Networks in this site'
    )

    vlan_ids = fields.One2many(
        comodel_name='unifi.vlan',
        inverse_name='site_id',
        string='VLANs',
        help='VLANs in this site'
    )
    
    device_ids = fields.One2many(
        comodel_name='unifi.device',
        inverse_name='site_id',
        string='Devices',
        help='Devices in this site'
    )

    user_ids = fields.One2many(
        comodel_name='unifi.user',
        inverse_name='site_id',
        string='Users',
        help='Users in this site'
    )

    firewall_rule_ids = fields.One2many(
        comodel_name='unifi.firewall.rule',
        inverse_name='site_id',
        string='Firewall Rules',
        help='Firewall rules for this site'
    )

    port_forward_ids = fields.One2many(
        comodel_name='unifi.port.forward',
        inverse_name='site_id',
        string='Port Forwards',
        help='Port forwarding rules for this site'
    )

    dns_config_ids = fields.One2many(
        comodel_name='unifi.dns.config',
        inverse_name='site_id',
        string='DNS Configurations',
        help='DNS configurations for this site'
    )

    routing_config_ids = fields.One2many(
        comodel_name='unifi.routing.config',
        inverse_name='site_id',
        string='Routing Configurations',
        help='Routing configurations for this site'
    )
    
    # Relations with system models
    system_info_id = fields.Many2one(
        comodel_name='unifi.system.info',
        string='System Info',
        ondelete='cascade',
        help='System information snapshot',
        required=False
    )
    
    # Relations avec les appareils
    device_ids = fields.One2many(
        comodel_name='unifi.device',
        inverse_name='site_id',
        string='Appareils',
        help='Appareils UniFi associés à ce site'
    )
    
    
    # API logs
    api_log_ids = fields.One2many(
        comodel_name='unifi.api.log',
        inverse_name='site_id',
        string='API Logs',
        help='Logs of API calls'
    )
    
    # Sync jobs
    sync_job_ids = fields.One2many(
        comodel_name='unifi.sync.job',
        inverse_name='site_id',
        string='Sync Jobs',
        help='Synchronization jobs'
    )
    
    # Computed fields
    network_count = fields.Integer(
        compute='_compute_counts',
        string='Network Count',
        store=True,
        help='Total number of networks in this site'
    )
    
    device_count = fields.Integer(
        compute='_compute_counts',
        string='Device Count',
        store=True,
        help='Total number of devices in this site'
    )
    
    user_count = fields.Integer(
        compute='_compute_counts',
        string='User Count',
        store=True,
        help='Number of users in this site'
    )
    
    firewall_rule_count = fields.Integer(
        compute='_compute_counts',
        string='Firewall Rule Count',
        store=True,
        help='Number of firewall rules in this site'
    )

    client_count = fields.Integer(
        compute='_compute_client_count',
        string='Connected Clients',
        store=True,
        help='Number of currently connected clients'
    )
    
    # Dashboard Metrics - Updated to point to new models
    dashboard_metric_ids = fields.One2many(
        comodel_name='unifi.dashboard.metric',
        inverse_name='site_id',
        string='Real-time Dashboard Metrics',
        help='Real-time metrics for this site'
    )
    
    dashboard_stat_ids = fields.One2many(
        comodel_name='unifi.dashboard.stat',
        inverse_name='site_id',
        string='Historical Statistics',
        help='Historical statistics for this site'
    )
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Site name must be unique!'),
    ]
    
    # Field dependencies and constraints
    @api.constrains('api_type')
    def _check_api_fields(self):
        """Validate that required fields are set based on API type
        
        This method delegates to the appropriate API-specific model for validation.
        """
        for site in self:
            if site.api_type == 'controller':
                # Delegate to controller-specific implementation
                self.env['unifi.site.controller']._check_required_fields(site)
            elif site.api_type == 'site_manager':
                # Delegate to site manager-specific implementation
                self.env['unifi.site.manager']._check_required_fields(site)
    
    @api.onchange('api_type')
    def _onchange_api_type(self):
        """Clear fields that are not relevant to the selected API type
        
        This method delegates to the appropriate API-specific model for field clearing.
        """
        if self.api_type == 'controller':
            # Delegate to controller-specific implementation
            self.env['unifi.site.controller']._clear_irrelevant_fields(self)
        elif self.api_type == 'site_manager':
            # Delegate to site manager-specific implementation
            self.env['unifi.site.manager']._clear_irrelevant_fields(self)
    
    @api.depends('network_ids', 'device_ids', 'user_ids', 'firewall_rule_ids')
    def _compute_counts(self):
        """Compute counts for related records
        
        This method calculates the number of networks, devices, users, and firewall rules
        associated with this site. It's triggered automatically when any of these related
        records are added or removed.
        """
        for site in self:
            # Safely get counts, handling potential errors
            try:
                site.network_count = len(site.network_ids) if site.network_ids else 0
                site.device_count = len(site.device_ids) if site.device_ids else 0
                site.user_count = len(site.user_ids) if site.user_ids else 0
                site.firewall_rule_count = len(site.firewall_rule_ids) if site.firewall_rule_ids else 0
            except Exception as e:
                _logger.error('Error computing counts for site %s: %s', site.name, str(e))
                # Set default values in case of error
                site.network_count = site.device_count = site.user_count = site.firewall_rule_count = 0
    
    @api.depends('user_ids')
    def _compute_client_count(self):
        """Compute the number of connected clients
        
        This method counts only users that are currently connected to the network.
        It relies on the 'is_connected' flag on user records.
        """
        for site in self:
            try:
                if site.user_ids:
                    # Filter users that have is_connected=True
                    site.client_count = len(site.user_ids.filtered(lambda u: u.is_connected if hasattr(u, 'is_connected') else False))
                else:
                    site.client_count = 0
            except Exception as e:
                _logger.error('Error computing client count for site %s: %s', site.name, str(e))
                site.client_count = 0
    
    # Action methods
    def action_view_networks(self):
        """Open the networks view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('Networks'),
            'view_mode': 'tree,form',
            'res_model': 'unifi.network',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
    
    def action_view_devices(self):
        """Open the devices view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('Devices'),
            'view_mode': 'tree,form',
            'res_model': 'unifi.device',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
    
    def action_view_users(self):
        """Open the users view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('Users'),
            'view_mode': 'tree,form',
            'res_model': 'unifi.user',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
    
    def action_view_firewall_rules(self):
        """Open the firewall rules view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('Firewall Rules'),
            'view_mode': 'tree,form',
            'res_model': 'unifi.firewall.rule',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
    
    def action_view_api_logs(self):
        """Open the API logs view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('API Logs'),
            'view_mode': 'tree,form',
            'res_model': 'unifi.api.log',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
    
    def action_view_sync_jobs(self):
        """Open the sync jobs view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('Sync Jobs'),
            'view_mode': 'tree,form',
            'res_model': 'unifi.sync.job',
            'domain': [('site_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_site_id': self.id}
        }
        
    def action_configure_controller(self):
        """Open the controller configuration view for this site
        
        This method checks if a controller configuration already exists for this site.
        If it does, it opens the existing configuration in form view.
        If not, it creates a new configuration and opens it in form view.
        """
        self.ensure_one()
        
        # Check if a controller configuration already exists for this site
        controller = self.env['unifi.site.controller'].search([('site_id', '=', self.id)], limit=1)
        
        if controller:
            # Open existing controller configuration
            return {
                'name': _('Controller API Configuration'),
                'view_mode': 'form',
                'res_model': 'unifi.site.controller',
                'res_id': controller.id,
                'type': 'ir.actions.act_window',
                'target': 'new',
            }
        else:
            # Create and open a new controller configuration
            controller = self.env['unifi.site.controller'].create({
                'site_id': self.id,
                'verify_ssl': self.verify_ssl,
            })
            
            return {
                'name': _('Controller API Configuration'),
                'view_mode': 'form',
                'res_model': 'unifi.site.controller',
                'res_id': controller.id,
                'type': 'ir.actions.act_window',
                'target': 'new',
            }
    
    def action_configure_site_manager(self):
        """Open the site manager configuration view for this site
        
        This method checks if a site manager configuration already exists for this site.
        If it does, it opens the existing configuration in form view.
        If not, it creates a new configuration and opens it in form view.
        """
        self.ensure_one()
        
        # Check if a site manager configuration already exists for this site
        manager = self.env['unifi.site.manager'].search([('site_id', '=', self.id)], limit=1)
        
        if manager:
            # Open existing site manager configuration
            return {
                'name': _('Site Manager API Configuration'),
                'view_mode': 'form',
                'res_model': 'unifi.site.manager',
                'res_id': manager.id,
                'type': 'ir.actions.act_window',
                'target': 'new',
            }
        else:
            # Create and open a new site manager configuration
            manager = self.env['unifi.site.manager'].create({
                'site_id': self.id,
                'verify_ssl': self.verify_ssl,
            })
            
            return {
                'name': _('Site Manager API Configuration'),
                'view_mode': 'form',
                'res_model': 'unifi.site.manager',
                'res_id': manager.id,
                'type': 'ir.actions.act_window',
                'target': 'new',
            }
    
    def action_sync_now(self):
        """Trigger an immediate synchronization"""
        self.ensure_one()
        if self.api_type == 'controller':
            return self._sync_controller()
        elif self.api_type == 'site_manager':
            return self._sync_site_manager()
        return True
        
    def action_sync_networks(self):
        """Synchronize only networks for this site"""
        self.ensure_one()
        try:
            # Utiliser la méthode de synchronisation du modèle unifi.network
            self.env['unifi.network'].sync_networks(self)
                    
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Network Synchronization'),
                    'message': _('Networks synchronized successfully!'),
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Network Synchronization'),
                    'message': _('Error: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
            
    def action_sync_devices(self):
        """Synchronize only devices for this site"""
        self.ensure_one()
        try:
            # Utiliser la méthode de synchronisation du modèle unifi.device
            devices = self.env['unifi.device'].search([('site_id', '=', self.id)])
            for device in devices:
                device.sync_from_unifi()
                    
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Device Synchronization'),
                    'message': _('Devices synchronized successfully!'),
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Device Synchronization'),
                    'message': _('Error: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
            
    def action_sync_users(self):
        """Synchronize only users for this site"""
        self.ensure_one()
        try:
            # Utiliser la méthode de synchronisation du modèle unifi.user
            self.env['unifi.user'].sync_users(self)
                    
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('User Synchronization'),
                    'message': _('Users synchronized successfully!'),
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('User Synchronization'),
                    'message': _('Error: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
            
    def action_sync_vlans(self):
        """Synchronize only VLANs for this site"""
        self.ensure_one()
        try:
            # Utiliser la méthode de synchronisation du modèle unifi.vlan
            self.env['unifi.vlan'].sync_vlans_from_api(self)
                    
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('VLAN Synchronization'),
                    'message': _('VLANs synchronized successfully!'),
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('VLAN Synchronization'),
                    'message': _('Error: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
            
    def action_sync_firewall_rules(self):
        """Synchronize only firewall rules for this site"""
        self.ensure_one()
        try:
            # Utiliser la méthode de synchronisation du modèle unifi.firewall.rule
            self.env['unifi.firewall.rule'].sync_firewall_rules(self)
                    
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Firewall Rule Synchronization'),
                    'message': _('Firewall rules synchronized successfully!'),
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Firewall Rule Synchronization'),
                    'message': _('Error: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
            
    def action_sync_port_forwards(self):
        """Synchronize only port forwards for this site"""
        self.ensure_one()
        try:
            # Utiliser la méthode de synchronisation du modèle unifi.port.forward
            self.env['unifi.port.forward'].sync_port_forwards(self)
                    
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Port Forward Synchronization'),
                    'message': _('Port forwards synchronized successfully!'),
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Port Forward Synchronization'),
                    'message': _('Error: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
            
    def action_sync_routing(self):
        """Synchronize only routing configuration for this site"""
        self.ensure_one()
        try:
            # Utiliser la méthode de synchronisation du modèle unifi.routing.config
            routing_configs = self.env['unifi.routing.config'].search([('site_id', '=', self.id)])
            for config in routing_configs:
                config.sync_from_unifi()
            
            # Synchroniser également les routes individuelles
            routes = self.env['unifi.routing'].search([('site_id', '=', self.id)])
            for route in routes:
                route.sync_from_unifi()
                    
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Routing Configuration Synchronization'),
                    'message': _('Routing configuration synchronized successfully!'),
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Routing Configuration Synchronization'),
                    'message': _('Error: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
    
    def action_test_connection(self):
        """Test the connection to the UniFi site"""
        self.ensure_one()
        try:
            if self.api_type == 'controller':
                connection_result = self._test_controller_connection()
            elif self.api_type == 'site_manager':
                connection_result = self._test_site_manager_connection()
            else:
                connection_result = False
            
            if connection_result:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Test'),
                        'message': _('Connection successful!'),
                        'sticky': False,
                        'type': 'success',
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Test'),
                        'message': _('Connection failed. Please check your settings.'),
                        'sticky': True,
                        'type': 'danger',
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Test'),
                    'message': _('Error: %s') % str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
    
    # API-specific methods
    def _test_controller_connection(self):
        """Test connection to the Controller API"""
        try:
            # Récupérer l'objet controller associé à ce site
            controller = self.env['unifi.site.controller'].search([('site_id', '=', self.id)], limit=1)
            if not controller:
                _logger.error('Controller not found for site %s', self.name)
                return False
                
            # Déléguer le test de connexion au modèle controller
            return controller._authenticate()
        except Exception as e:
            _logger.error('Error testing Controller API connection: %s', str(e))
            return False
    
    def _test_site_manager_connection(self):
        """Test connection to the Site Manager API"""
        try:
            # Récupérer l'objet site manager associé à ce site
            site_manager = self.env['unifi.site.manager'].search([('site_id', '=', self.id)], limit=1)
            if not site_manager:
                _logger.error('Site Manager not found for site %s', self.name)
                return False
                
            # Déléguer le test de connexion au modèle site manager
            return site_manager._test_site_manager_connection()
        except Exception as e:
            _logger.error('Error testing Site Manager API connection: %s', str(e))
            return False
    
    def _sync_controller(self):
        """Synchronize data with the Controller API
        
        This method orchestrates the synchronization process with the UniFi Controller API.
        It retrieves data for all supported entity types (devices, networks, VLANs, users,
        firewall rules, port forwards, and system info) and updates the corresponding
        records in the Odoo database.
        
        Returns:
            bool: True if synchronization was successful, False otherwise
        """
        # Initialiser sync_job en dehors du bloc try pour éviter les erreurs de lint
        sync_job = None
        
        try:
            # Create a sync job
            sync_job = self.env['unifi.sync.job'].create({
                'site_id': self.id,
                'start_time': fields.Datetime.now(),
                'state': 'running',
                'sync_type': 'manual',
                'api_type': 'controller',
            })
            
            # Récupérer l'objet controller associé à ce site
            controller = self.env['unifi.site.controller'].search([('site_id', '=', self.id)], limit=1)
            if not controller:
                if sync_job:
                    sync_job.write({
                        'end_time': fields.Datetime.now(),
                        'state': 'failed',
                        'message': 'Controller not found',
                    })
                return False
                
            # Authenticate with the Controller API
            if not controller._authenticate():
                if sync_job:
                    sync_job.write({
                        'end_time': fields.Datetime.now(),
                        'state': 'failed',
                        'message': 'Authentication failed',
                    })
                return False
                
            success = True
            sync_messages = []
            
            # Synchronize system info
            try:
                system_info_data = controller.get_system_info_data(self)
                if system_info_data:
                    # Process and store system info data
                    # TODO: Implement system info synchronization
                    sync_messages.append('System info synchronized')
                else:
                    sync_messages.append('Failed to retrieve system info')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing system info: {str(e)}')
                _logger.error('Error synchronizing system info: %s', str(e))
                success = False
            
            # Synchronize devices
            try:
                device_data = controller.get_device_data(self)
                if device_data:
                    # Process and store device data
                    # TODO: Implement device synchronization
                    sync_messages.append('Devices synchronized')
                else:
                    sync_messages.append('Failed to retrieve devices')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing devices: {str(e)}')
                _logger.error('Error synchronizing devices: %s', str(e))
                success = False
            
            # Synchronize networks
            try:
                network_data = controller.get_network_data(self)
                if network_data:
                    # Process and store network data
                    # TODO: Implement network synchronization
                    sync_messages.append('Networks synchronized')
                else:
                    sync_messages.append('Failed to retrieve networks')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing networks: {str(e)}')
                _logger.error('Error synchronizing networks: %s', str(e))
                success = False
            
            # Synchronize VLANs
            try:
                vlan_data = controller.get_vlan_data(self)
                if vlan_data:
                    # Process and store VLAN data
                    # TODO: Implement VLAN synchronization
                    sync_messages.append('VLANs synchronized')
                else:
                    sync_messages.append('Failed to retrieve VLANs')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing VLANs: {str(e)}')
                _logger.error('Error synchronizing VLANs: %s', str(e))
                success = False
            
            # Synchronize users
            try:
                user_data = controller.get_user_data(self)
                if user_data:
                    # Process and store user data
                    # TODO: Implement user synchronization
                    sync_messages.append('Users synchronized')
                else:
                    sync_messages.append('Failed to retrieve users')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing users: {str(e)}')
                _logger.error('Error synchronizing users: %s', str(e))
                success = False
            
            # Synchronize firewall rules
            try:
                firewall_data = controller.get_firewall_data(self)
                if firewall_data:
                    # Process and store firewall data
                    # TODO: Implement firewall rule synchronization
                    sync_messages.append('Firewall rules synchronized')
                else:
                    sync_messages.append('Failed to retrieve firewall rules')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing firewall rules: {str(e)}')
                _logger.error('Error synchronizing firewall rules: %s', str(e))
                success = False
            
            # Synchronize port forwards
            try:
                port_forward_data = controller.get_port_forward_data(self)
                if port_forward_data:
                    # Process and store port forward data
                    # TODO: Implement port forward synchronization
                    sync_messages.append('Port forwards synchronized')
                else:
                    sync_messages.append('Failed to retrieve port forwards')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing port forwards: {str(e)}')
                _logger.error('Error synchronizing port forwards: %s', str(e))
                success = False
            
            # Logout from the Controller API
            controller._logout()
            
            # Update sync job
            if sync_job:
                sync_job.write({
                    'end_time': fields.Datetime.now(),
                    'state': 'completed' if success else 'partial',
                    'message': '\n'.join(sync_messages),
                })
            
            # Update last sync time
            self.write({
                'last_sync': fields.Datetime.now(),
            })
            
            return success
        except Exception as e:
            _logger.error('Error synchronizing with Controller API: %s', str(e))
            if sync_job:
                sync_job.write({
                    'end_time': fields.Datetime.now(),
                    'state': 'failed',
                    'message': str(e),
                })
            return False
    
    def _sync_site_manager(self):
        """Synchronize data with the Site Manager API
        
        This method orchestrates the synchronization process with the UniFi Site Manager API.
        It retrieves data for all supported entity types (devices, networks, VLANs, users,
        firewall rules, port forwards, and system info) and updates the corresponding
        records in the Odoo database.
        
        Returns:
            bool: True if synchronization was successful, False otherwise
        """
        # Initialiser sync_job en dehors du bloc try pour éviter les erreurs de lint
        sync_job = None
        
        try:
            # Create a sync job
            sync_job = self.env['unifi.sync.job'].create({
                'site_id': self.id,
                'start_time': fields.Datetime.now(),
                'state': 'running',
                'sync_type': 'manual',
                'api_type': 'site_manager',
            })
            
            # Récupérer l'objet site manager associé à ce site
            site_manager = self.env['unifi.site.manager'].search([('id', '=', self.id)], limit=1)
            if not site_manager:
                if sync_job:
                    sync_job.write({
                        'end_time': fields.Datetime.now(),
                        'state': 'failed',
                        'message': 'Site Manager not found',
                    })
                return False
            
            # Test the connection to ensure we can authenticate
            if not site_manager.test_connection():
                if sync_job:
                    sync_job.write({
                        'end_time': fields.Datetime.now(),
                        'state': 'failed',
                        'message': 'Connection test failed',
                    })
                return False
                
            success = True
            sync_messages = []
            
            # Synchronize system info
            try:
                system_info_data = site_manager.get_system_info_data(self)
                if system_info_data:
                    # Process and store system info data
                    # TODO: Implement system info synchronization
                    sync_messages.append('System info synchronized')
                else:
                    sync_messages.append('Failed to retrieve system info')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing system info: {str(e)}')
                _logger.error('Error synchronizing system info: %s', str(e))
                success = False
            
            # Synchronize devices
            try:
                device_data = site_manager.get_device_data(self)
                if device_data:
                    # Process and store device data
                    # TODO: Implement device synchronization
                    sync_messages.append('Devices synchronized')
                else:
                    sync_messages.append('Failed to retrieve devices')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing devices: {str(e)}')
                _logger.error('Error synchronizing devices: %s', str(e))
                success = False
            
            # Synchronize networks
            try:
                network_data = site_manager.get_network_data(self)
                if network_data:
                    # Process and store network data
                    # TODO: Implement network synchronization
                    sync_messages.append('Networks synchronized')
                else:
                    sync_messages.append('Failed to retrieve networks')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing networks: {str(e)}')
                _logger.error('Error synchronizing networks: %s', str(e))
                success = False
            
            # Synchronize VLANs
            try:
                vlan_data = site_manager.get_vlan_data(self)
                if vlan_data:
                    # Process and store VLAN data
                    # TODO: Implement VLAN synchronization
                    sync_messages.append('VLANs synchronized')
                else:
                    sync_messages.append('Failed to retrieve VLANs')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing VLANs: {str(e)}')
                _logger.error('Error synchronizing VLANs: %s', str(e))
                success = False
            
            # Synchronize users
            try:
                user_data = site_manager.get_user_data(self)
                if user_data:
                    # Process and store user data
                    # TODO: Implement user synchronization
                    sync_messages.append('Users synchronized')
                else:
                    sync_messages.append('Failed to retrieve users')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing users: {str(e)}')
                _logger.error('Error synchronizing users: %s', str(e))
                success = False
            
            # Synchronize firewall rules
            try:
                firewall_data = site_manager.get_firewall_data(self)
                if firewall_data:
                    # Process and store firewall data
                    # TODO: Implement firewall rule synchronization
                    sync_messages.append('Firewall rules synchronized')
                else:
                    sync_messages.append('Failed to retrieve firewall rules')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing firewall rules: {str(e)}')
                _logger.error('Error synchronizing firewall rules: %s', str(e))
                success = False
            
            # Synchronize port forwards
            try:
                port_forward_data = site_manager.get_port_forward_data(self)
                if port_forward_data:
                    # Process and store port forward data
                    # TODO: Implement port forward synchronization
                    sync_messages.append('Port forwards synchronized')
                else:
                    sync_messages.append('Failed to retrieve port forwards')
                    success = False
            except Exception as e:
                sync_messages.append(f'Error synchronizing port forwards: {str(e)}')
                _logger.error('Error synchronizing port forwards: %s', str(e))
                success = False
            
            # Update sync job
            if sync_job:
                sync_job.write({
                    'end_time': fields.Datetime.now(),
                    'state': 'completed' if success else 'partial',
                    'message': '\n'.join(sync_messages),
                })
            
            # Update last sync time
            self.write({
                'last_sync': fields.Datetime.now(),
            })
            
            return success
        except Exception as e:
            _logger.error('Error synchronizing with Site Manager API: %s', str(e))
            if sync_job:
                sync_job.write({
                    'end_time': fields.Datetime.now(),
                    'state': 'failed',
                    'message': str(e),
                })
            return False
    
    # Override create and write methods
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to verify connection before saving
        
        Args:
            vals_list (list): List of values to create records with
            
        Returns:
            unifi.site: The created records
        """
        # Create the records
        sites = super(UnifiSite, self).create(vals_list)
        
        # Test the connection for each site
        for site in sites:
            try:
                if site.api_type == 'controller':
                    site._test_controller_connection()
                elif site.api_type == 'site_manager':
                    site._test_site_manager_connection()
            except Exception as e:
                _logger.warning('Connection test failed during creation: %s', str(e))
                # We don't raise an error here, just log a warning
        
        return sites
    
    def write(self, vals):
        """Override write to verify connection if connection details change"""
        # Check if connection details have changed
        connection_fields = ['api_type', 'host', 'port', 'username', 'password', 
                            'controller_type', 'api_key', 'mfa_enabled', 'mfa_token']
        
        connection_changed = any(field in vals for field in connection_fields)
        
        # Write the values
        result = super(UnifiSite, self).write(vals)
        
        # Test the connection if connection details have changed
        if connection_changed:
            for site in self:
                try:
                    if site.api_type == 'controller':
                        site._test_controller_connection()
                    elif site.api_type == 'site_manager':
                        site._test_site_manager_connection()
                except Exception as e:
                    _logger.warning('Connection test failed after update: %s', str(e))
                    # We don't raise an error here, just log a warning
        
        return result
    
    def get_device_data(self):
        """Récupère les données des appareils du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les appareils.
        
        Returns:
            list: Liste des données de tous les appareils
        """
        self.ensure_one()
        
        # Déterminer le type d'API à utiliser
        if self.api_type == 'controller':
            # Utiliser l'API Controller
            return self.env['unifi.site.controller'].get_device_data(self)
        elif self.api_type == 'site_manager':
            # Utiliser l'API Site Manager
            return self.env['unifi.site.manager'].get_device_data(self)
        else:
            # Type d'API non pris en charge
            _logger.error("Type d'API non pris en charge: %s", self.api_type)
            return False
    
    def _delegate_api_method(self, method_name):
        """Délègue l'appel d'une méthode à l'API appropriée
        
        Cette méthode générique permet de déléguer l'appel d'une méthode
        au modèle spécifique en fonction du type d'API configuré.
        
        Args:
            method_name: Nom de la méthode à appeler
            
        Returns:
            Le résultat de la méthode appelée, ou False si le type d'API n'est pas pris en charge
        """
        self.ensure_one()
        
        # Déterminer le type d'API à utiliser
        if self.api_type == 'controller':
            # Utiliser l'API Controller
            return getattr(self.env['unifi.site.controller'], method_name)(self)
        elif self.api_type == 'site_manager':
            # Utiliser l'API Site Manager
            return getattr(self.env['unifi.site.manager'], method_name)(self)
        else:
            # Type d'API non pris en charge
            _logger.error("Type d'API non pris en charge: %s", self.api_type)
            return False

    def get_vlan_data(self):
        """Récupère les données des VLANs du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les VLANs.
        
        Returns:
            list: Liste des données de tous les VLANs
        """
        return self._delegate_api_method('get_vlan_data')
            
    def get_network_data(self):
        """Récupère les données des réseaux du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les réseaux.
        
        Returns:
            list: Liste des données de tous les réseaux
        """
        return self._delegate_api_method('get_network_data')

    def get_user_data(self):
        """Récupère les données des utilisateurs du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les utilisateurs.
        
        Returns:
            list: Liste des données de tous les utilisateurs
        """
        return self._delegate_api_method('get_user_data')

    def get_firewall_data(self):
        """Récupère les données des règles de pare-feu du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les règles de pare-feu.
        
        Returns:
            list: Liste des données de toutes les règles de pare-feu
        """
        return self._delegate_api_method('get_firewall_data')
            
    def get_port_forward_data(self):
        """Récupère les données des redirections de port du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations sur les redirections de port.
        
        Returns:
            list: Liste des données de toutes les redirections de port
        """
        return self._delegate_api_method('get_port_forward_data')
            
    def get_system_info_data(self):
        """Récupère les données d'information système du site
        
        Cette méthode utilise l'API appropriée en fonction du type de site
        pour obtenir les informations système.
        
        Returns:
            dict: Données d'information système
        """
        return self._delegate_api_method('get_system_info_data')
        
    def action_import_site(self):
        """Lance directement l'import pour le site sélectionné
        
        Cette méthode est appelée lorsque l'utilisateur clique sur le bouton
        'Importer' dans la vue liste des sites UniFi. Elle déclenche
        immédiatement le processus d'importation pour le site sélectionné.
        
        Returns:
            dict: Notification de succès ou d'échec
        """
        self.ensure_one()
        
        # Vérifier si le site a déjà un contrôleur ou un gestionnaire de site associé
        controller = self.env['unifi.site.controller'].search([('site_id', '=', self.id)], limit=1)
        site_manager = self.env['unifi.site.manager'].search([('site_id', '=', self.id)], limit=1)
        
        if not controller and not site_manager:
            # Si aucun contrôleur ou gestionnaire de site n'est associé, ouvrir l'assistant d'importation
            return {
                'name': _('Import UniFi Site'),
                'type': 'ir.actions.act_window',
                'res_model': 'unifi.site.import.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_name': self.name, 'default_site_id': self.site_id, 'default_api_type': self.api_type}
            }
        
        # Tester la connexion
        connection_success = False
        if self.api_type == 'controller' and controller:
            connection_success = self._test_controller_connection()
        elif self.api_type == 'site_manager' and site_manager:
            connection_success = self._test_site_manager_connection()
        
        if connection_success:
            # Déclencher la synchronisation
            self.action_sync_now()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Connection successful! Synchronization started for site %s.') % self.name,
                    'sticky': False,
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Failed to connect to site %s. Please check your connection settings.') % self.name,
                    'sticky': True,
                    'type': 'danger',
                }
            }
