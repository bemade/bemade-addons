# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
import random
from datetime import timedelta

_logger = logging.getLogger(__name__)

class UdmSite(models.Model):
    """Represents a UniFi site managed by one or more UDM Pro
    
    This model is the central entity that groups all UniFi configurations and devices.
    Each site can have multiple configurations, devices, networks, and users.
    """
    _name = 'udm.site'
    _description = 'UniFi Site'
    _order = 'name'
    _inherit = ['mail.thread']
    
    # Basic site information
    name = fields.Char(string='Name', required=True, tracking=True,
                      help='Site name')
    site_id = fields.Char(string='Site ID',
                         help="Site identifier in UniFi (usually 'default')",
                         default='default',
                         readonly=True,
                         required=True)
    description = fields.Text(string='Description', tracking=True,
                            help='Site description')
    address = fields.Text(string='Physical Address', tracking=True,
                         help='Physical location of this site')
    active = fields.Boolean(string='Active', default=True, tracking=True,
                          help='Indicates if this site is currently active')
    
    # Controller configuration
    controller_type = fields.Selection([
        ('udm', 'UDM/UDR'),
        ('software', 'Software Controller')
    ], string='Controller Type', required=True, default='udm', tracking=True,
        help='Type of UniFi controller managing this site')
    
    host = fields.Char(string='Host', required=True, tracking=True,
                      help='IP address or hostname of the controller')
    port = fields.Integer(string='Port', default=443, required=True,
                         help='Port number (default: 443)')
    username = fields.Char(string='Username', required=True, tracking=True)
    password = fields.Char(string='Password', required=True)
    mfa_token = fields.Char(string='MFA Token',
                           help='Two-factor authentication token if enabled')
    
    # Configuration data
    timestamp = fields.Datetime(string='Last Update', tracking=True)
    raw_data = fields.Text(string='Raw Data',
                          help='Raw configuration data in JSON format')
    
    # Related Records
    configuration_ids = fields.One2many('udm.configuration', 'site_id',
                                      string='Configurations',
                                      help='Configurations for this site')
    network_ids = fields.One2many('udm.network', 'site_id',
                                 string='Networks',
                                 help='Networks in this site')
    vlan_ids = fields.One2many('udm.vlan', 'site_id',
                              string='VLANs',
                              help='VLANs in this site')
    device_ids = fields.One2many('udm.device', 'site_id',
                                string='Devices',
                                help='Devices in this site')
    user_ids = fields.One2many('udm.user', 'site_id',
                              string='Users',
                              help='Users in this site')
    firewall_rule_ids = fields.One2many('udm.firewall.rule', 'site_id',
                                       string='Firewall Rules',
                                       help='Firewall rules for this site')
    port_forward_ids = fields.One2many('udm.port.forward', 'site_id',
                                      string='Port Forwards',
                                      help='Port forwarding rules for this site')
    dns_config_ids = fields.One2many('udm.dns.config', 'site_id',
                                    string='DNS Configurations',
                                    help='DNS configurations for this site')
    routing_config_ids = fields.One2many('udm.routing.config', 'site_id',
                                        string='Routing Configurations',
                                        help='Routing configurations for this site')
    
    # Dashboard Metrics
    dashboard_metric_ids = fields.One2many('udm.dashboard.metric', 'site_id',
                                         string='Dashboard Metrics',
                                         help='Real-time metrics for this site')
    dashboard_stat_ids = fields.One2many('udm.dashboard.stat', 'site_id',
                                        string='Statistics',
                                        help='Historical statistics for this site')
    
    # Computed Fields
    config_count = fields.Integer(compute='_compute_counts',
                                string='Configuration Count',
                                help='Number of configurations in this site')
    device_count = fields.Integer(compute='_compute_device_count',
                                string='Total Devices',
                                help='Total number of devices in this site')
    client_count = fields.Integer(compute='_compute_client_count',
                                string='Connected Clients',
                                help='Number of currently connected clients')
    
    @api.depends('configuration_ids')
    def _compute_counts(self):
        """Compute the number of configurations in this site"""
        for site in self:
            site.config_count = len(site.configuration_ids)
    
    @api.depends('device_ids')
    def _compute_device_count(self):
        """Compute the total number of devices in this site"""
        for site in self:
            site.device_count = len(site.device_ids)
    
    @api.depends('user_ids')
    def _compute_client_count(self):
        """Compute the number of connected clients"""
        for site in self:
            site.client_count = len(site.user_ids.filtered(lambda u: u.is_connected))
    
    def action_view_configurations(self):
        """Open the configurations view filtered for this site"""
        self.ensure_one()
        return {
            'name': _('Configurations'),
            'type': 'ir.actions.act_window',
            'res_model': 'udm.configuration',
            'view_mode': 'tree,form',
            'domain': [('site_id', '=', self.id)],
            'context': {'default_site_id': self.id},
        }
    
    def action_view_dashboard(self):
        """Display the dashboard for this site"""
        self.ensure_one()
        return {
            'name': _('Site Dashboard'),
            'type': 'ir.actions.act_window',
            'res_model': 'udm.dashboard',
            'view_mode': 'kanban,form',
            'domain': [('site_id', '=', self.id)],
            'context': {'default_site_id': self.id},
        }
    
    def action_refresh_metrics(self):
        """Refresh the dashboard metrics and statistics for this site"""
        self.ensure_one()
        for config in self.configuration_ids:
            config.action_update_dashboard_metrics()
            
    _sql_constraints = [
        ('name_uniq', 'unique(name)',
         'Site name must be unique!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to verify connection before saving"""
        for vals in vals_list:
            if not self._verify_connection(vals):
                raise UserError(_('Could not connect to the UniFi controller. '
                                'Please verify your credentials and connection details.'))
        return super(UdmSite, self).create(vals_list)

    def write(self, vals):
        """Override write to verify connection if connection details change"""
        if any(field in vals for field in ['host', 'port', 'username',
                                         'password', 'mfa_token']):
            for record in self:
                test_vals = {**record.copy_data()[0], **vals}
                if not self._verify_connection(test_vals):
                    raise UserError(_('Could not connect to the UniFi controller. '
                                    'Please verify your credentials and connection details.'))
        return super(UdmSite, self).write(vals)

    def _verify_connection(self, vals):
        """Verify connection to the UniFi controller
        
        Args:
            vals (dict): Values to use for connection test
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Build base URL based on controller type
            base_url = f"https://{vals['host']}:{vals.get('port', 443)}"
            if vals.get('controller_type') == 'software':
                base_url += '/api'
            else:
                base_url += '/proxy/network'

            # Disable SSL verification warning
            import urllib3
            urllib3.disable_warnings()
            
            # Try to authenticate
            session = requests.Session()
            response = session.post(
                f"{base_url}/api/auth/login",
                json={
                    'username': vals['username'],
                    'password': vals['password'],
                    'remember': True,
                    'token': vals.get('mfa_token', '')
                },
                verify=False
            )
            
            if response.status_code == 200:
                return True
                
            _logger.error(
                "Authentication failed for UniFi controller at %s: %s",
                vals['host'],
                response.text
            )
            return False
            
        except Exception as e:
            _logger.error(
                "Error connecting to UniFi controller at %s: %s",
                vals['host'],
                str(e)
            )
            return False
