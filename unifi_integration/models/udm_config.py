# -*- coding: utf-8 -*-

# These imports will work in an Odoo environment, even if your IDE marks them as not found
# pylint: disable=import-error
from odoo import models, fields, api, _
from odoo.exceptions import UserError
# pylint: enable=import-error

import json
import logging
import random
import requests
import urllib3
from datetime import datetime, timedelta
from requests.exceptions import RequestException

_logger = logging.getLogger(__name__)

class UdmSite(models.Model):
    """Represents a UniFi site managed by one or more UDM Pro"""
    _name = 'udm.site'
    _description = 'UDM Site'
    _order = 'name'
    
    name = fields.Char(string='Name', required=True)
    site_id = fields.Char(string='Site ID', help="Site identifier in UniFi (always 'default')", default='default', readonly=True, required=True)
    description = fields.Text(string='Description')
    address = fields.Text(string='Physical Address')
    active = fields.Boolean(string='Active', default=True)
    
    # Relations
    configuration_ids = fields.One2many('udm.configuration', 'site_id', string='Configurations')
    dashboard_metric_ids = fields.One2many('udm.dashboard.metric', 'site_id', string='Dashboard Metrics')
    dashboard_stat_ids = fields.One2many('udm.dashboard.stat', 'site_id', string='Statistics')
    
    # Counters
    config_count = fields.Integer(compute='_compute_counts', string='Configuration Count')
    device_count = fields.Integer(compute='_compute_device_count', string='Total Devices')
    client_count = fields.Integer(compute='_compute_client_count', string='Connected Clients')
    
    @api.depends('network_ids')
    def _compute_counts(self):
        """Compute the number of networks in this site"""
        for record in self:
            record.config_count = len(record.network_ids)
    
    @api.depends('device_ids')
    def _compute_device_count(self):
        """Compute the total number of devices in this site"""
        for record in self:
            record.device_count = len(record.device_ids)
    
    @api.depends('user_ids')
    def _compute_client_count(self):
        """Compute the number of connected clients"""
        for record in self:
            record.client_count = len(record.user_ids.filtered(lambda u: u.status == 'connected'))
    
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
        """Refreshes the dashboard metrics and statistics for this site"""
        self.ensure_one()
        configs = self.configuration_ids.filtered(lambda c: c.active)
        if not configs:
            raise UserError(_('No active UDM Pro configuration found for this site'))
            
        # Call the UDM Pro API to get real metrics
        try:
            for config in configs:
                config._fetch_metrics()
        except Exception as e:
            raise UserError(_('Failed to fetch metrics: %s') % str(e))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    
    def _generate_sample_metrics(self):
        """Generates demo metrics for the dashboard"""
        # Delete old metrics
        self.dashboard_metric_ids.unlink()
        
        # Types of metrics to generate
        metric_types = [
            'bandwidth_usage', 'cpu_usage', 'memory_usage', 'clients_count',
            'wan_status', 'threat_count', 'device_status'
        ]
        
        # Generate new metrics
        metrics_vals = []
        now = fields.Datetime.now()
        
        for metric_type in metric_types:
            # Generate current value
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
        """Generates historical data for graphs"""
        data = []
        for _ in range(points):  # Using _ to indicate an unused variable
            if integer:
                value = random.randint(min_val, max_val)
            else:
                value = random.uniform(min_val, max_val)
                value = round(value, 2)
            data.append(value)
        return json.dumps(data)
    
    def _generate_sample_statistics(self):
        """Generates demo statistics for historical data"""
        # Delete old statistics
        self.dashboard_stat_ids.unlink()
        
        # Types of statistics to generate
        stat_types = [
            'bandwidth_usage',  # Total bandwidth used
            'client_count',     # Number of clients over time
            'threat_blocked',   # Number of security threats blocked
            'device_uptime'     # Device uptime duration
        ]
        
        # Generate statistics for the last 30 days
        today = fields.Date.today()
        start_date = today - timedelta(days=30)
        
        # Generate new statistics
        stats_vals = []
        
        for day in range(31):  # 31 days of data
            date = start_date + timedelta(days=day)
            
            for stat_type in stat_types:
                # Generate value and unit based on type
                stat_value = 0.0
                stat_unit = ''
                
                if stat_type == 'bandwidth_usage':
                    stat_value = random.uniform(100, 1000)  # GB per day
                    stat_unit = 'bytes'
                elif stat_type == 'client_count':
                    stat_value = random.randint(10, 100)
                    stat_unit = 'count'
                elif stat_type == 'threat_blocked':
                    stat_value = random.randint(0, 20)
                    stat_unit = 'count'
                elif stat_type == 'device_uptime':
                    stat_value = random.uniform(20, 24)  # Hours per day
                    stat_unit = 'hours'
                
                # Add daily statistic
                stats_vals.append({
                    'site_id': self.id,
                    'date': date,
                    'stat_type': stat_type,
                    'value': stat_value,
                    'unit': stat_unit,
                    'is_aggregate': False
                })
                
                # Add weekly aggregate every 7 days
                if day % 7 == 0:
                    stats_vals.append({
                        'site_id': self.id,
                        'date': date,
                        'stat_type': stat_type,
                        'value': stat_value * 7,  # Simple multiplication for demo
                        'unit': stat_unit,
                        'is_aggregate': True,
                        'aggregate_type': 'sum',
                        'time_start': fields.Datetime.to_datetime(date),
                        'time_end': fields.Datetime.to_datetime(date + timedelta(days=7))
                    })
        
        # Create the statistics
        for vals in stats_vals:
            self.env['udm.dashboard.stat'].create(vals)


class UdmPortForward(models.Model):
    """Port forwarding rules for the UDM Pro"""
    _name = 'udm.port.forward'
    _description = 'UDM Pro Port Forward Rule'
    
    name = fields.Char(string='Name', required=True)
    enabled = fields.Boolean(string='Enabled', default=True)
    src_port = fields.Char(string='Source Port')
    dst_port = fields.Char(string='Destination Port')
    protocol = fields.Selection([
        ('tcp', 'TCP'),
        ('udp', 'UDP'),
        ('both', 'TCP & UDP'),
    ], string='Protocol', default='tcp')
    dst_address = fields.Char(string='Destination Address')
    raw_data = fields.Text(string='Raw Data')
    
    # Relations
    config_id = fields.Many2one('udm.configuration', string='Configuration', ondelete='cascade', required=True)

class UdmDnsConfig(models.Model):
    """DNS configuration for the UDM Pro"""
    _name = 'udm.dns.config'
    _description = 'UDM Pro DNS Configuration'
    
    enabled = fields.Boolean(string='Enabled', default=True)
    filters_enabled = fields.Boolean(string='Content Filtering Enabled', default=False)
    custom_dns = fields.Char(string='Custom DNS Servers')
    raw_data = fields.Text(string='Raw Data')
    
    # Relations
    config_id = fields.Many2one('udm.configuration', string='Configuration', ondelete='cascade', required=True)

class UdmRoutingConfig(models.Model):
    """Routing configuration for the UDM Pro"""
    _name = 'udm.routing.config'
    _description = 'UDM Pro Routing Configuration'
    
    ospf_enabled = fields.Boolean(string='OSPF Enabled', default=False)
    static_routes = fields.Text(string='Static Routes')
    raw_data = fields.Text(string='Raw Data')
    
    # Relations
    config_id = fields.Many2one('udm.configuration', string='Configuration', ondelete='cascade', required=True)

class UdmConfiguration(models.Model):
    def _get_base_url(self):
        """Get the base URL for the UDM Pro API"""
        return f'https://{self.host}:{self.port}'

    def _get_api_url(self, endpoint):
        """Get the full URL for a UDM Pro API endpoint
        
        This method handles the URL generation for different API endpoints.
        Authentication and system endpoints don't need the /proxy/network prefix,
        while all other endpoints require it.
        
        Args:
            endpoint (str): API endpoint path (e.g. '/api/auth/login')
            
        Returns:
            str: Complete URL for the API endpoint
        """
        # Add /proxy/network prefix for all endpoints except auth
        if not endpoint.startswith('/api/auth/'):
            endpoint = f'/proxy/network{endpoint}'
            
        url = f'{self._get_base_url()}{endpoint}'
        _logger.debug('Generated URL: %s', url)
        return url

    def _get_api_headers(self, csrf_token=None):
        """Get headers for UniFi API requests
        
        Generates the necessary headers for API requests to the UDM Pro.
        All requests use JSON format and identify themselves as the Odoo UniFi Integration.
        For authenticated endpoints, a CSRF token is included in the headers.
        
        Args:
            csrf_token (str, optional): CSRF token required for authenticated requests
            
        Returns:
            dict: Dictionary containing the required headers for the API request
        """
        # Basic headers required for all requests
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Odoo UniFi Integration/1.0'
        }
        
        # Add CSRF token for authenticated requests
        if csrf_token:
            headers['X-CSRF-Token'] = csrf_token
            _logger.debug('Adding CSRF token to headers')
            
        _logger.debug('Generated API headers: %s', headers)
        return headers

    def _login(self):
        """Login to UniFi OS and get authentication cookie and CSRF token
        
        This method handles the authentication process with the UDM Pro:
        1. Validates login credentials
        2. Gets CSRF token
        3. Performs login with CSRF token
        4. Handles MFA if required
        
        Returns:
            dict: A dictionary containing the session cookies and CSRF token
            
        Raises:
            UserError: If authentication fails or MFA is required but not provided
        """
        _logger.info('Starting connection to UDM Pro')
        _logger.debug('Connection parameters - Host: %s, Port: %s, User: %s', 
                      self.host, self.port, self.username)
        
        # Validate required credentials
        if not self.host or not self.username or not self.password:
            _logger.error('Missing connection information: host=%s, username=%s, password=%s', 
                         bool(self.host), bool(self.username), bool(self.password))
            raise UserError(_('Please provide host, username and password'))

        # Disable SSL warnings - UDM Pro often uses self-signed certificates
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Create session and disable SSL verification
        session = requests.Session()
        session.verify = False

        try:
            _logger.info('Attempting to connect to UniFi OS API...')
            
            # Prepare login data
            login_data = {
                'username': self.username,
                'password': self.password,
                'rememberMe': True
            }
            
            # Add MFA token if present
            if self.mfa_token:
                login_data['token'] = self.mfa_token
                _logger.debug('Adding MFA token to login data')

            # Set required headers for UniFi OS
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Odoo UniFi Integration/1.0'
            }

            _logger.debug('Connection details: %s', {
                'url': self._get_api_url('/api/auth/login'),
                'username': self.username,
                'host': self.host,
                'port': self.port
            })

            # Attempt login
            response = session.post(
                self._get_api_url('/api/auth/login'),
                json=login_data,
                headers=headers,
                verify=False,
                timeout=10
            )
            
            # Check response status
            response.raise_for_status()
            
            # Check if MFA is required
            if response.status_code == 403 and 'x-factor-required' in response.headers:
                _logger.info('Two-factor authentication required')
                raise UserError(_('Please provide two-factor authentication code'))
            
            # Get CSRF token from response headers
            csrf_token = response.headers.get('X-CSRF-Token', '')
            
            _logger.info('Successfully connected to UDM Pro')
            _logger.debug('Received cookies: %s', dict(session.cookies))
            
            # Return session and CSRF token
            return {
                'session': session,
                'csrf_token': csrf_token
            }
            
        except RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                error_msg = e.response.text
                try:
                    error_data = json.loads(error_msg)
                    if e.response.status_code == 401:
                        error_message = error_data.get('error', {}).get('message', '')
                        raise UserError(_('Authentication failed: %s\n\nPlease check:\n1. Username and password are correct\n2. User exists in UniFi OS\n3. User has sufficient permissions') % error_message)
                    elif e.response.status_code == 403:
                        raise UserError(_('Access denied. Please verify your permissions.'))
                except json.JSONDecodeError:
                    pass
            _logger.error('Login failed: %s', error_msg)
            raise UserError(_('Connection to UDM Pro failed: %s') % error_msg)

    def _fetch_metrics(self):
        """Fetch real-time metrics from the UDM Pro
        
        Returns:
            dict: System and network metrics
            
        Raises:
            UserError: If connection fails or metrics are inaccessible
        """
        try:
            # Get authenticated session
            auth = self._login()
            if not auth:
                raise UserError(_('Unable to authenticate with UDM Pro'))
                
            session = auth.get('session')
            csrf_token = auth.get('csrf_token')
            if not session or not csrf_token:
                raise UserError(_('Missing session or CSRF token'))

            # Set headers for API requests
            headers = self._get_api_headers(csrf_token)

            # Get system statistics
            system_response = session.get(
                self._get_api_url('/api/system/stats'),
                headers=headers
            )
            system_response.raise_for_status()
            system_stats = system_response.json()

            # Get client information
            clients_response = session.get(
                self._get_api_url('/api/site/default/clients'),
                headers=headers
            )
            clients_response.raise_for_status()
            clients = clients_response.json()

            # Get network statistics
            network_response = session.get(
                self._get_api_url('/api/site/default/devices'),
                headers=headers
            )
            network_response.raise_for_status()
            network_stats = network_response.json()

            # Prepare metrics
            metrics_vals = [
                {
                    'site_id': self.site_id.id,
                    'metric_type': 'cpu_usage',
                    'current_value': str(system_stats.get('data', {}).get('cpu', {}).get('usage', 0)),
                    'max_value': '100',
                    'last_update': fields.Datetime.now(),
                    'description': 'CPU Usage'
                },
                {
                    'site_id': self.site_id.id,
                    'metric_type': 'memory_usage',
                    'current_value': str(system_stats.get('data', {}).get('memory', {}).get('used_percentage', 0)),
                    'max_value': '100',
                    'last_update': fields.Datetime.now(),
                    'description': 'Memory Usage'
                },
                {
                    'site_id': self.site_id.id,
                    'metric_type': 'client_count',
                    'current_value': str(len(clients.get('data', []))),
                    'max_value': '1000',
                    'last_update': fields.Datetime.now(),
                    'description': 'Connected Clients'
                },
                {
                    'site_id': self.site_id.id,
                    'metric_type': 'network_throughput',
                    'current_value': str(sum(d.get('tx_bytes', 0) + d.get('rx_bytes', 0) 
                                          for d in network_stats.get('data', []))),
                    'max_value': str(1e9),  # 1 Gbps
                    'last_update': fields.Datetime.now(),
                    'description': 'Total Network Throughput'
                }
            ]
            
            # Get historical statistics
            history_response = session.get(
                self._get_api_url('/api/site/default/statistics/5minutes'),
                headers=headers
            )
            history_response.raise_for_status()
            history_stats = history_response.json()
            
            # Create historical statistics
            stats_vals = []
            now = fields.Datetime.now()
            
            for stat in history_stats.get('data', []):
                # Get timestamp and ensure it's valid
                try:
                    timestamp = fields.Datetime.from_string(stat.get('time')) or now
                except (ValueError, TypeError):
                    timestamp = now
                    _logger.warning('Invalid timestamp detected in historical statistics')
                
                stats_vals.append({
                    'site_id': self.site_id.id,
                    'timestamp': fields.Datetime.to_string(timestamp),
                    'rx_bytes': stat.get('rx_bytes', 0),
                    'tx_bytes': stat.get('tx_bytes', 0),
                    'num_sta': stat.get('num_sta', 0),
                    'cpu_usage': system_stats.get('data', {}).get('cpu', {}).get('usage', 0),
                    'memory_usage': system_stats.get('data', {}).get('memory', {}).get('used_percentage', 0)
                })
            
            # Update metrics and statistics
            self.env['udm.dashboard.metric'].search([('site_id', '=', self.site_id.id)]).unlink()
            self.env['udm.dashboard.metric'].create(metrics_vals)
            
            self.env['udm.dashboard.stat'].search([('site_id', '=', self.site_id.id)]).unlink()
            self.env['udm.dashboard.stat'].create(stats_vals)
            
            _logger.info('Metrics and statistics updated successfully')
            
        except RequestException as e:
            _logger.error('Error fetching metrics: %s', str(e))
            raise UserError(_('Unable to fetch metrics from UDM Pro: %s') % str(e))
    """Complete UDM Pro configuration stored in Odoo"""
    _name = 'udm.configuration'
    _description = 'UDM Pro Configuration'
    _order = 'timestamp desc'
    
    name = fields.Char(string='Name', compute='_compute_name', store=True)
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now, required=True)
    raw_data = fields.Text(string='Raw Data', help="Raw configuration data in JSON format")
    active = fields.Boolean(string='Active', default=True, help="Indicates if this configuration is currently active")
    
    # UDM Pro Connection
    host = fields.Char(string='Host', help="IP address or hostname of the UDM Pro")
    port = fields.Integer(string='Port', default=443)
    username = fields.Char(string='Username')
    password = fields.Char(string='Password')
    mfa_token = fields.Char(string='MFA Code', help="Two-factor authentication code received by email")
    
    # Relations
    site_id = fields.Many2one('udm.site', string='Site', required=True,
                             ondelete='restrict',
                             help='Site this configuration belongs to')
    system_info_id = fields.Many2one('udm.system.info', string='System Info',
                                    ondelete='cascade',
                                    help='System information snapshot')
    network_ids = fields.One2many('udm.network', 'site_id', string='Networks',
                                 help='Networks in this site')
    vlan_ids = fields.One2many('udm.vlan', 'site_id', string='VLANs',
                              help='VLANs in this site')
    device_ids = fields.One2many('udm.device', 'site_id', string='Devices',
                                help='Devices in this site')
    user_ids = fields.One2many('udm.user', 'site_id', string='Users',
                              help='Users in this site')
    settings_id = fields.Many2one('udm.settings', string='Settings',
                                 ondelete='cascade',
                                 help='Site settings')
    firewall_rule_ids = fields.One2many('udm.firewall.rule', 'site_id',
                                       string='Firewall Rules',
                                       help='Firewall rules for this site')
    port_forward_ids = fields.One2many('udm.port.forward', 'site_id',
                                      string='Port Forwards',
                                      help='Port forwarding rules for this site')
    dns_config_id = fields.Many2one('udm.dns.config', string='DNS Configuration',
                                   ondelete='cascade',
                                   help='DNS settings')
    routing_config_id = fields.Many2one('udm.routing.config',
                                       string='Routing Configuration',
                                       ondelete='cascade',
                                       help='Routing settings')
    
    # Statistics
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
        """Open the networks view filtered for this site
        
        Returns a window action to display the list of networks
        associated with this site.
        """
        self.ensure_one()
        return {
            'name': _('Networks'),
            'view_mode': 'tree,form',
            'res_model': 'udm.network',
            'domain': [('site_id', '=', self.site_id.id)],
            'type': 'ir.actions.act_window',
        }
    
    def action_view_devices(self):
        """Open the devices view filtered for this site
        
        Returns a window action to display the list of devices
        associated with this site.
        """
        self.ensure_one()
        return {
            'name': _('Devices'),
            'view_mode': 'tree,form',
            'res_model': 'udm.device',
            'domain': [('site_id', '=', self.site_id.id)],
            'type': 'ir.actions.act_window',
        }
    
    def action_view_users(self):
        """Open the users view filtered for this site
        
        Returns a window action to display the list of users
        associated with this site.
        """
        self.ensure_one()
        return {
            'name': _('Users'),
            'view_mode': 'tree,form',
            'res_model': 'udm.user',
            'domain': [('site_id', '=', self.site_id.id)],
            'type': 'ir.actions.act_window',
        }
    
    def action_view_firewall_rules(self):
        """Open the firewall rules view filtered for this site
        
        Returns a window action to display the list of firewall rules
        associated with this site.
        """
        self.ensure_one()
        return {
            'name': _('Firewall Rules'),
            'view_mode': 'tree,form',
            'res_model': 'udm.firewall.rule',
            'domain': [('site_id', '=', self.site_id.id)],
            'type': 'ir.actions.act_window',
        }
    
    def action_import_configuration(self):
        """Import configuration from UDM Pro device.
        
        This method is called when the user clicks the Import button in the
        import configuration wizard. It performs the following steps:
        
        1. Validates that all required connection information is provided
        2. Connects to the UDM Pro device using the provided credentials
        3. If MFA is required, opens the MFA wizard
        4. Once authenticated, retrieves the current configuration from the device
        5. Imports the configuration into Odoo using import_configuration()
        6. Returns an action to view the imported configuration
        
        Returns:
            dict: An action to display the imported configuration or the MFA wizard
        
        Raises:
            UserError: If any required connection information is missing
        """
        self.ensure_one()
        
        # Validate that all required connection information is provided
        if not all([self.host, self.port, self.username, self.password]):
            raise UserError(_('Please provide host, username, password and port'))
        
        try:
            # Try to connect
            auth = self._login()
            if not auth:
                raise UserError(_('Unable to authenticate with UDM Pro'))
            session = auth.get('session')
            csrf_token = auth.get('csrf_token')
            if not session or not csrf_token:
                raise UserError(_('Missing session or CSRF token'))
        except UserError as e:
            if 'two-factor authentication' in str(e):
                # Open MFA wizard
                return {
                    'name': _('Two-Factor Authentication Code'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'udm.mfa.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_config_id': self.id
                    }
                }
            raise

        try:
            config_data = {}
            
            # Get site context first
            _logger.info('Getting site context...')
            response = session.get(
                self._get_api_url('/api/s/default/self'),
                headers=self._get_api_headers(csrf_token),
                verify=False
            )
            if response.status_code != 200:
                _logger.error('Failed to get site context: %s', response.text)
                raise UserError(_('Failed to access site. Please check your credentials.'))

            # Fetch system info
            _logger.info('Retrieving system information...')
            response = session.get(
                self._get_api_url('/api/s/default/stat/sysinfo'),
                headers=self._get_api_headers(csrf_token),
                verify=False
            )
            _logger.info('API response (status: %s): %s', response.status_code, response.text)
            
            system_info = response.json()
            _logger.info('System data received: %s', system_info)
            
            system_info_data = system_info.get('data')
            if isinstance(system_info_data, list):
                # Si les données sont dans une liste, prenons le premier élément
                system_info_data = system_info_data[0] if system_info_data else {}
            elif not isinstance(system_info_data, dict):
                system_info_data = {}
                
            if not system_info_data:
                _logger.error('No system data received in response')
                raise UserError(_('Failed to retrieve system information from UDM Pro'))
            config_data['system_info'] = system_info_data
            
            # Fetch networks
            _logger.info('Retrieving networks...')
            response = session.get(
                self._get_api_url('/api/s/default/rest/setting/network'),
                headers=self._get_api_headers(csrf_token),
                verify=False
            )
            _logger.info('API response (status: %s): %s', response.status_code, response.text)
            networks = response.json()
            networks_data = networks.get('data')
            if isinstance(networks_data, list):
                # Handle list format
                config_data['networks'] = {'networks': networks_data}
            elif isinstance(networks_data, dict):
                # Handle dictionary format
                config_data['networks'] = {'networks': [networks_data]}
            else:
                _logger.error('No network data received in response')
                raise UserError(_('Failed to retrieve networks from UDM Pro'))
            
            # Fetch VLANs
            _logger.info('Retrieving VLANs...')
            response = session.get(
                self._get_api_url('/api/s/default/rest/setting/network'),
                headers=self._get_api_headers(csrf_token),
                verify=False
            )
            _logger.info('API response (status: %s): %s', response.status_code, response.text)
            vlans = response.json()
            vlans_data = vlans.get('data')
            if isinstance(vlans_data, list):
                # Handle list format
                config_data['vlans'] = {'vlans': vlans_data}
            elif isinstance(vlans_data, dict):
                # Handle dictionary format
                config_data['vlans'] = {'vlans': [vlans_data]}
            else:
                _logger.error('No VLAN data received in response')
                raise UserError(_('Failed to retrieve VLANs from UDM Pro'))
            
            # Fetch devices
            _logger.info('Retrieving devices...')
            response = session.get(
                self._get_api_url('/api/s/default/stat/device-basic'),
                headers=self._get_api_headers(csrf_token),
                verify=False
            )
            _logger.info('API response (status: %s): %s', response.status_code, response.text)
            devices = response.json()
            devices_data = devices.get('data')
            if isinstance(devices_data, list):
                # Handle list format
                config_data['devices'] = {'devices': devices_data}
            elif isinstance(devices_data, dict):
                # Handle dictionary format
                config_data['devices'] = {'devices': [devices_data]}
            else:
                _logger.error('No device data received in response')
                raise UserError(_('Failed to retrieve devices from UDM Pro'))
            
            # Fetch users
            _logger.info('Retrieving users...')
            response = session.get(
                self._get_api_url('/api/s/default/rest/user'),
                headers=self._get_api_headers(csrf_token),
                verify=False
            )
            _logger.info('API response (status: %s): %s', response.status_code, response.text)
            users = response.json()
            users_data = users.get('data')
            if isinstance(users_data, list):
                # Handle list format
                config_data['users'] = {'users': users_data}
            elif isinstance(users_data, dict):
                # Handle dictionary format
                config_data['users'] = {'users': [users_data]}
            else:
                _logger.error('No user data received in response')
                raise UserError(_('Failed to retrieve users from UDM Pro'))
            
            # Fetch settings
            _logger.info('Retrieving settings...')
            response = session.get(
                self._get_api_url('/api/s/default/rest/setting'),
                headers=self._get_api_headers(csrf_token),
                verify=False
            )
            _logger.info('API response (status: %s): %s', response.status_code, response.text)
            settings = response.json()
            settings_data = settings.get('data')
            if isinstance(settings_data, list):
                # Handle list format
                config_data['settings'] = {'settings': settings_data}
            elif isinstance(settings_data, dict):
                # Handle dictionary format
                config_data['settings'] = {'settings': [settings_data]}
            else:
                _logger.error('No settings data received in response')
                raise UserError(_('Failed to retrieve settings from UDM Pro'))
            
            # Fetch firewall rules
            _logger.info('Retrieving firewall rules...')
            response = session.get(
                self._get_api_url('/api/s/default/rest/firewallrule'),
                headers=self._get_api_headers(csrf_token),
                verify=False
            )
            _logger.info('API response (status: %s): %s', response.status_code, response.text)
            firewall_rules = response.json()
            firewall_rules_data = firewall_rules.get('data')
            if isinstance(firewall_rules_data, list):
                # Handle list format
                config_data['firewall_rules'] = {'rules': firewall_rules_data}
            elif isinstance(firewall_rules_data, dict):
                # Handle dictionary format
                config_data['firewall_rules'] = {'rules': [firewall_rules_data]}
            else:
                _logger.error('No firewall rule data received in response')
                raise UserError(_('Failed to retrieve firewall rules from UDM Pro'))
            
            # Fetch port forwarding rules
            _logger.info('Retrieving port forwarding rules...')
            response = session.get(
                self._get_api_url('/api/s/default/rest/portforward'),
                headers=self._get_api_headers(csrf_token),
                verify=False
            )
            _logger.info('API response (status: %s): %s', response.status_code, response.text)
            port_forwards = response.json()
            port_forwards_data = port_forwards.get('data')
            if isinstance(port_forwards_data, list):
                # Handle list format
                config_data['port_forwards'] = {'port_forwards': port_forwards_data}
            elif isinstance(port_forwards_data, dict):
                # Handle dictionary format
                config_data['port_forwards'] = {'port_forwards': [port_forwards_data]}
            else:
                _logger.error('No port forwarding data received in response')
                raise UserError(_('Failed to retrieve port forwarding rules from UDM Pro'))
            
            # Fetch DNS configuration
            _logger.info('Retrieving DNS configuration...')
            response = session.get(
                self._get_api_url('/api/s/default/rest/setting/dns'),
                headers=self._get_api_headers(csrf_token),
                verify=False
            )
            _logger.info('API response (status: %s): %s', response.status_code, response.text)
            dns_config = response.json()
            dns_config_data = dns_config.get('data')
            if isinstance(dns_config_data, list):
                # Handle list format
                config_data['dns_config'] = {'dns_config': dns_config_data}
            elif isinstance(dns_config_data, dict):
                # Handle dictionary format
                config_data['dns_config'] = {'dns_config': [dns_config_data]}
            else:
                _logger.error('No DNS configuration data received in response')
                raise UserError(_('Failed to retrieve DNS configuration from UDM Pro'))
            
            # Fetch routing configuration
            _logger.info('Retrieving routing configuration...')
            response = session.get(
                self._get_api_url('/api/s/default/stat/routing'),
                headers=self._get_api_headers(csrf_token),
                verify=False
            )
            _logger.info('API response (status: %s): %s', response.status_code, response.text)
            routing_config = response.json()
            routing_config_data = routing_config.get('data')
            if isinstance(routing_config_data, list):
                # Handle list format
                config_data['routing'] = {'routing': routing_config_data}
            elif isinstance(routing_config_data, dict):
                # Handle dictionary format
                config_data['routing'] = {'routing': [routing_config_data]}
            else:
                _logger.error('No routing configuration data received in response')
                raise UserError(_('Failed to retrieve routing configuration from UDM Pro'))
            
        except RequestException as e:
            raise UserError(_('Failed to retrieve configuration from UDM Pro: %s') % str(e))
        
        # Import the configuration using the model's import method
        config = self.import_configuration(config_data)
        
        # Return an action to display the imported configuration
        return {
            'type': 'ir.actions.act_window',
            'name': _('Configuration importée'),
            'res_model': 'udm.configuration',
            'res_id': config.id,
            'view_mode': 'form',
            'target': 'current'
        }
    
    @api.model
    def import_configuration(self, config_data):
        """
        Imports a complete UDM Pro configuration into Odoo
        
        Args:
            config_data (dict): Raw configuration data from the API
        
        Returns:
            int: ID of the created configuration
        """
        if not config_data:
            raise UserError(_("Please provide configuration data"))
        
        # Create the main configuration
        vals = {
            'timestamp': datetime.now(),
            'raw_data': json.dumps(config_data, indent=2, ensure_ascii=False),
        }
        
        config = self.create(vals)
        
        # Create system information
        system_info_data = config_data.get('system_info', {}).get('system_info')
        if isinstance(system_info_data, list):
            # Si les données sont dans une liste, prenons le premier élément
            system_info_data = system_info_data[0] if system_info_data else {}
        elif not isinstance(system_info_data, dict):
            system_info_data = {}
            
        if system_info_data:
            system_info = self.env['udm.system.info'].create({
                'site_id': config.site_id.id,
                'hostname': system_info_data.get('hostname', ''),
                'version': system_info_data.get('version', ''),
                'model': system_info_data.get('model', ''),
                'uptime': system_info_data.get('uptime', 0),
                'serial': system_info_data.get('serialNumber', ''),
                'mac_address': system_info_data.get('mac', '') or system_info_data.get('macAddress', ''),
                'raw_data': json.dumps(system_info_data, indent=2, ensure_ascii=False),
            })
            config.system_info_id = system_info.id
        
        # Create networks
        networks_data = config_data.get('networks', {}).get('networks', [])
        for network_data in networks_data:
            if isinstance(network_data, dict):
                # Create network with all available fields
                self.env['udm.network'].create({
                    'site_id': config.site_id.id,
                    'name': network_data.get('name', ''),
                    'purpose': network_data.get('purpose', 'corporate'),
                    'subnet': network_data.get('subnet', ''),
                    'vlan_id_number': network_data.get('vlanId'),
                    'dhcp_enabled': network_data.get('dhcpEnabled', False),
                    'dhcp_start': network_data.get('dhcpStart', ''),
                    'dhcp_stop': network_data.get('dhcpStop', ''),
                    'domain_name': network_data.get('domainName', ''),
                    'raw_data': json.dumps(network_data, indent=2, ensure_ascii=False),
                })
        
        # Create VLANs
        vlans_data = config_data.get('networks', {}).get('vlans', [])
        for vlan_data in vlans_data:
            if isinstance(vlan_data, dict):
                # Create VLAN with all available fields
                self.env['udm.vlan'].create({
                    'site_id': config.site_id.id,
                    'vlan_id': vlan_data.get('id', 0),
                    'name': vlan_data.get('name', ''),
                    'enabled': vlan_data.get('enabled', True),
                    'raw_data': json.dumps(vlan_data, indent=2, ensure_ascii=False)
                })
        
        # Create devices
        devices_data = config_data.get('devices', {}).get('devices', [])
        for device_data in devices_data:
            if isinstance(device_data, dict):
                # Determine device type based on model or type
                device_type = device_data.get('type', '')
                if not device_type:
                    model = device_data.get('model', '').lower()
                    if 'uap' in model or 'ap' in model:
                        device_type = 'uap'
                    elif 'usw' in model or 'switch' in model:
                        device_type = 'usw'
                    elif 'ugw' in model or 'gateway' in model:
                        device_type = 'ugw'
                    elif 'udm' in model or 'dream' in model:
                        device_type = 'udm'
                    else:
                        device_type = 'client'
                
                # Create device with all available fields
                self.env['udm.device'].create({
                    'site_id': config.site_id.id,
                    'name': device_data.get('name', ''),
                    'mac_address': device_data.get('mac', ''),
                    'ip_address': device_data.get('ip', ''),
                    'device_type': device_type,
                    'model': device_data.get('model', ''),
                    'last_seen': datetime.fromtimestamp(device_data.get('lastSeen', 0)),
                    'raw_data': json.dumps(device_data, indent=2, ensure_ascii=False),
                })
        
        # Create users
        users_data = config_data.get('users', {}).get('users', [])
        for user_data in users_data:
            if isinstance(user_data, dict):
                self.env['udm.user'].create({
                    'site_id': config.site_id.id,
                    'name': user_data.get('name', ''),
                    'email': user_data.get('email', ''),
                    'role': user_data.get('role', ''),
                    'enabled': user_data.get('enabled', True),
                    'mac_address': user_data.get('mac', ''),
                    'ip_address': user_data.get('ip', ''),
                    'network_id': self.env['udm.network'].search([('site_id', '=', config.site_id.id), ('name', '=', user_data.get('network', ''))]).id,
                    'last_seen': datetime.fromtimestamp(user_data.get('lastSeen', 0)),
                    'raw_data': json.dumps(user_data, indent=2, ensure_ascii=False),
                })
        
        # Create settings
        settings_data = config_data.get('settings', {})
        if settings_data:
            # Extract system settings
            system_settings = settings_data.get('system', {})
            dns_settings = settings_data.get('dns', {})
            services = settings_data.get('services', {})
            
            # Create settings record with all available fields
            settings = self.env['udm.settings'].create({
                'site_id': config.site_id.id,
                'timezone': system_settings.get('timezone', 'America/Montreal'),
                
                # Time settings
                'ntp_enabled': system_settings.get('ntp', {}).get('enabled', True),
                'ntp_servers': ','.join(system_settings.get('ntp', {}).get('servers', [])),
                
                # DNS settings
                'dns_enabled': dns_settings.get('enabled', True),
                'dns_servers': ','.join(dns_settings.get('servers', [])),
                'dns_forwarding': dns_settings.get('forwarding', {}).get('enabled', True),
                
                # Advanced settings
                'upnp_enabled': services.get('upnp', {}).get('enabled', False),
                'mdns_enabled': services.get('mdns', {}).get('enabled', True),
                'igmp_proxy': services.get('igmp_proxy', {}).get('enabled', False),
                
                # Raw data for debugging and future reference
                'raw_data': json.dumps(settings_data, indent=2, ensure_ascii=False),
            })
            config.settings_id = settings.id
            
        # Create port forwarding rules
        port_forward_data = config_data.get('port_forwards', {}).get('data', [])
        for rule_data in port_forward_data:
            if isinstance(rule_data, dict):
                self.env['udm.port.forward'].create({
                    'site_id': config.site_id.id,
                    'name': rule_data.get('name', ''),
                    'enabled': rule_data.get('enabled', True),
                    'src_port': str(rule_data.get('fwd', '')),
                    'dst_port': str(rule_data.get('port', '')),
                    'protocol': rule_data.get('proto', '').lower(),
                    'dst_address': rule_data.get('dst', ''),
                    'raw_data': json.dumps(rule_data, indent=2, ensure_ascii=False),
                })
        
        # Create DNS configuration
        dns_config_data = config_data.get('dns_config', {}).get('data', {})
        if dns_config_data:
            dns_config = self.env['udm.dns.config'].create({
                'site_id': config.site_id.id,  # Lier directement au site
                'enabled': dns_config_data.get('system', {}).get('unifi', {}).get('enabled', True),
                'filters_enabled': dns_config_data.get('system', {}).get('unifi', {}).get('content_filtering_enabled', False),
                'custom_dns': ','.join([str(server) for server in dns_config_data.get('system', {}).get('nameservers', [])]),
                'raw_data': json.dumps(dns_config_data, indent=2, ensure_ascii=False),
            })
            config.dns_config_id = dns_config.id
        
        # Create firewall rules
        firewall_rules_data = config_data.get('firewall', {}).get('rules', [])
        for rule_data in firewall_rules_data:
            if isinstance(rule_data, dict):
                # Create firewall rule with all available fields
                self.env['udm.firewall.rule'].create({
                    'site_id': config.site_id.id,  # Lier directement au site
                    'name': rule_data.get('name', ''),
                    'description': rule_data.get('description', ''),
                    'enabled': rule_data.get('enabled', True),
                    'sequence': rule_data.get('sequence', 10),
                    'action': rule_data.get('action', 'drop').lower(),
                    'protocol': rule_data.get('protocol', 'all').lower(),
                    'source': rule_data.get('source', ''),
                    'destination': rule_data.get('destination', ''),
                    'src_port': rule_data.get('src_port', ''),
                    'dst_port': rule_data.get('dst_port', ''),
                    'raw_data': json.dumps(rule_data, indent=2, ensure_ascii=False)
                })
        
        # Create routing configuration
        routing_config_data = config_data.get('routing', {}).get('data', {})
        if routing_config_data:
            routing_config = self.env['udm.routing.config'].create({
                'site_id': config.site_id.id,  # Lier directement au site
                'ospf_enabled': routing_config_data.get('ospf', {}).get('enabled', False),
                'static_routes': ','.join([f"{route.get('network')}/{route.get('prefix')} via {route.get('nexthop')}" for route in routing_config_data.get('static_routes', [])]),
                'raw_data': json.dumps(routing_config_data, indent=2, ensure_ascii=False),
            })
            config.routing_config_id = routing_config.id
        
        # Create firewall rules
        firewall_data = config_data.get('firewall_rules', {}).get('rules', [])
        for rule_data in firewall_data:
            if isinstance(rule_data, dict):
                self.env['udm.firewall.rule'].create({
                    'site_id': config.site_id.id,
                    'name': rule_data.get('name', ''),
                    'description': rule_data.get('description', ''),
                    'action': rule_data.get('action', 'drop'),
                    'protocol': rule_data.get('protocol', ''),
                    'source': rule_data.get('source', ''),
                    'destination': rule_data.get('destination', ''),
                    'enabled': rule_data.get('enabled', True),
                    'raw_data': json.dumps(rule_data, indent=2, ensure_ascii=False),
                })
        
        # Log successful import
        _logger.info('Successfully imported UDM Pro configuration: %s', config.name)
        
        return config
    
    def action_compare_with(self):
        """Opens a wizard to compare this configuration with another"""
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
        """Duplicates this configuration"""
        self.ensure_one()
        
        # Create a new configuration by copying the raw data
        new_config = self.copy({
            'timestamp': datetime.now(),
            'name': _('%s (Duplicate)') % self.name,
        })
        
        return {
            'name': _('Duplicated Configuration'),
            'type': 'ir.actions.act_window',
            'res_model': 'udm.configuration',
            'res_id': new_config.id,
            'view_mode': 'form',
        }
    
    def action_generate_report(self):
        """Generates a PDF report of this configuration"""
        self.ensure_one()
        return {
            'type': 'ir.actions.report',
            'report_name': 'unifi_integration.report_udm_configuration',
            'report_type': 'qweb-pdf',
            'res_model': self._name,
            'res_id': self.id,
        }
        
    def action_view_dashboard(self):
        """Displays the dashboard for this configuration's site"""
        self.ensure_one()
        if not self.site_id:
            raise UserError(_('Configuration not linked to a site. Please select a site first.'))
            
        return {
            'name': _('Site Dashboard'),
            'view_mode': 'dashboard,form',
            'res_model': 'udm.site',
            'res_id': self.site_id.id,
            'type': 'ir.actions.act_window',
        }
        
    def action_update_dashboard_metrics(self):
        """Updates the dashboard metrics for this configuration's site"""
        self.ensure_one()
        if not self.site_id:
            raise UserError(_('Configuration not linked to a site. Please select a site first.'))
            
        # Call the site's metric refresh method
        return self.site_id.action_refresh_metrics()
        
    def unlink(self):
        """Override unlink method to handle configuration deletion properly"""
        for record in self:
            # Suppression des enregistrements liés avec ondelete='cascade'
            if record.system_info_id:
                record.system_info_id.unlink()
            if record.settings_id:
                record.settings_id.unlink()
            if record.dns_config_id:
                record.dns_config_id.unlink()
            if record.routing_config_id:
                record.routing_config_id.unlink()
                
            # Suppression des enregistrements One2many
            record.network_ids.unlink()
            record.vlan_ids.unlink()
            record.device_ids.unlink()
            record.user_ids.unlink()
            record.firewall_rule_ids.unlink()
            record.port_forward_ids.unlink()
        
        # Appel de la méthode unlink standard
        return super(UdmConfiguration, self).unlink()
