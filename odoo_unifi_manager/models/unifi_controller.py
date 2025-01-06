"""UniFi Controller Model."""
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from .unifi_api_client import UnifiApiClient
import logging
from datetime import timedelta
import json

_logger = logging.getLogger(__name__)

class UnifiController(models.Model):
    _name = 'unifi.ctrl'  # Gardé le même nom pour la compatibilité
    _description = 'UniFi Controller Configuration'

    name = fields.Char(
        string='Name',
        required=True
    )

    ip_address = fields.Char(
        string='IP Address',
        required=True,
        help="IP address of the UniFi Controller."
    )

    api_port = fields.Integer(
        string='API Port',
        default=8443,
        help="Port used for the UniFi API."
    )

    username = fields.Char(
        string='Username',
        required=True,
        help="Username for API authentication."
    )

    password = fields.Char(
        string='Password',
        required=True,
        help="Password for API authentication."
    )

    controller_type = fields.Selection(
        [
            ('udm', 'UDM Pro'),
            ('controller', 'Controller')
        ],
        string="Controller Type",
        default='udm',
        required=True,
        help="Select whether this is a UDM Pro or a UniFi Controller."
    )

    verify_ssl = fields.Boolean(
        string='Verify SSL',
        default=False,
        help="Enable SSL certificate verification."
    )
    
    last_sync = fields.Datetime(
        string='Last Synchronization',
        readonly=True
    )

    sync_interval = fields.Integer(
        string='Sync Interval (minutes)',
        default=60,
        help="How often to synchronize with the UniFi controller"
    )

    # Dashboard Fields
    total_clients = fields.Integer(
        string='Total Clients',
        compute='_compute_dashboard_data'
    )
    active_clients = fields.Integer(
        string='Active Clients',
        compute='_compute_dashboard_data'
    )
    total_devices = fields.Integer(
        string='Total Devices',
        compute='_compute_dashboard_data'
    )
    offline_devices = fields.Integer(
        string='Offline Devices',
        compute='_compute_dashboard_data'
    )
    total_bandwidth = fields.Float(
        string='Total Bandwidth (Mbps)',
        compute='_compute_dashboard_data'
    )
    bandwidth_usage = fields.Float(
        string='Bandwidth Usage (%)',
        compute='_compute_dashboard_data'
    )
    active_alerts = fields.Integer(
        string='Active Alerts',
        compute='_compute_dashboard_data'
    )
    critical_alerts = fields.Integer(
        string='Critical Alerts',
        compute='_compute_dashboard_data'
    )
    client_type_chart = fields.Json(
        string='Client Type Chart Data',
        compute='_compute_dashboard_data'
    )
    bandwidth_chart = fields.Json(
        string='Bandwidth Chart Data',
        compute='_compute_dashboard_data'
    )
    active_firewall_rules = fields.Integer(
        string='Active Firewall Rules',
        compute='_compute_dashboard_data'
    )
    blocked_connections = fields.Integer(
        string='Blocked Connections',
        compute='_compute_dashboard_data'
    )
    vpn_status = fields.Selection([
        ('up', 'Up'),
        ('down', 'Down'),
        ('partial', 'Partial')
    ], string='VPN Status',
        compute='_compute_dashboard_data'
    )
    threat_count = fields.Integer(
        string='Threat Count',
        compute='_compute_dashboard_data'
    )

    @api.model
    def get_dashboard_data(self):
        """Get dashboard data for the first controller."""
        controller = self.search([], limit=1)
        if not controller:
            return {
                'total_clients': 0,
                'active_clients': 0,
                'total_devices': 0,
                'offline_devices': 0,
                'total_bandwidth': 0,
                'bandwidth_usage': 0,
                'active_alerts': 0,
                'critical_alerts': 0,
                'client_type_chart': self._get_empty_client_chart(),
                'bandwidth_chart': self._get_empty_bandwidth_chart(),
                'active_firewall_rules': 0,
                'blocked_connections': 0,
                'vpn_status': 'No VPN',
                'threat_count': 0
            }

        try:
            with controller._get_unifi_client() as client:
                # Get clients data
                clients = client.list_clients() or []
                active_clients = [c for c in clients if c.get('is_wired') or c.get('is_wireless')]
                
                # Get devices data
                devices = client.list_devices() or []
                offline_devices = [d for d in devices if not d.get('state', 1)]
                
                # Get alerts
                alerts = client.list_alerts() or []
                critical_alerts = [a for a in alerts if a.get('severity', 'info') == 'critical']

                # Get firewall rules
                firewall_rules = client.list_firewall_rules() or []
                active_rules = [r for r in firewall_rules if r.get('enabled', False)]

                # Prepare client type data for chart
                client_types = {
                    'Wired': len([c for c in clients if c.get('is_wired')]),
                    'Wireless': len([c for c in clients if c.get('is_wireless')]),
                    'Guest': len([c for c in clients if c.get('is_guest')])
                }

                # Prepare bandwidth data (example data)
                bandwidth_data = {
                    'labels': ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00'],
                    'datasets': [
                        {
                            'label': 'Download',
                            'data': [30, 45, 60, 75, 90, 100],
                            'borderColor': '#00ff00',
                            'fill': False
                        },
                        {
                            'label': 'Upload',
                            'data': [20, 35, 45, 55, 65, 75],
                            'borderColor': '#0000ff',
                            'fill': False
                        }
                    ]
                }

                return {
                    'total_clients': len(clients),
                    'active_clients': len(active_clients),
                    'total_devices': len(devices),
                    'offline_devices': len(offline_devices),
                    'total_bandwidth': sum(d.get('tx_bytes', 0) + d.get('rx_bytes', 0) for d in devices),
                    'bandwidth_usage': sum(d.get('tx_rate', 0) + d.get('rx_rate', 0) for d in devices) / 1000000,  # Convert to Mbps
                    'active_alerts': len(alerts),
                    'critical_alerts': len(critical_alerts),
                    'client_type_chart': {
                        'labels': list(client_types.keys()),
                        'datasets': [{
                            'data': list(client_types.values()),
                            'backgroundColor': ['#FF6384', '#36A2EB', '#FFCE56']
                        }]
                    },
                    'bandwidth_chart': bandwidth_data,
                    'active_firewall_rules': len(active_rules),
                    'blocked_connections': sum(r.get('counters', {}).get('blocked', 0) for r in firewall_rules),
                    'vpn_status': 'Active' if any(d.get('vpn', False) for d in devices) else 'Inactive',
                    'threat_count': sum(1 for a in alerts if a.get('category') == 'security')
                }

        except Exception as e:
            _logger.error("Error fetching dashboard data: %s", str(e))
            return self._get_empty_dashboard_data()

    def _get_empty_client_chart(self):
        """Return empty client chart data structure."""
        return {
            'labels': ['Wired', 'Wireless', 'Guest'],
            'datasets': [{
                'data': [0, 0, 0],
                'backgroundColor': ['#FF6384', '#36A2EB', '#FFCE56']
            }]
        }

    def _get_empty_bandwidth_chart(self):
        """Return empty bandwidth chart data structure."""
        return {
            'labels': ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00'],
            'datasets': [
                {
                    'label': 'Download',
                    'data': [0, 0, 0, 0, 0, 0],
                    'borderColor': '#00ff00',
                    'fill': False
                },
                {
                    'label': 'Upload',
                    'data': [0, 0, 0, 0, 0, 0],
                    'borderColor': '#0000ff',
                    'fill': False
                }
            ]
        }

    def _get_empty_dashboard_data(self):
        """Return empty dashboard data structure."""
        return {
            'total_clients': 0,
            'active_clients': 0,
            'total_devices': 0,
            'offline_devices': 0,
            'total_bandwidth': 0,
            'bandwidth_usage': 0,
            'active_alerts': 0,
            'critical_alerts': 0,
            'client_type_chart': self._get_empty_client_chart(),
            'bandwidth_chart': self._get_empty_bandwidth_chart(),
            'active_firewall_rules': 0,
            'blocked_connections': 0,
            'vpn_status': 'No Connection',
            'threat_count': 0
        }

    def get_client(self):
        """Get an authenticated UniFi client instance"""
        _logger.info(f"Creating UniFi client for controller {self.name}")
        _logger.info(f"IP Address: {self.ip_address}, Port: {self.api_port}")
        _logger.info(f"Controller Type: {self.controller_type}")
        
        return UnifiApiClient(
            host=self.ip_address,
            port=self.api_port,
            username=self.username,
            password=self.password,
            is_udm=(self.controller_type == 'udm'),
            verify_ssl=self.verify_ssl,
            timeout=30  # Increase timeout to 30 seconds
        )

    def action_test_connection(self):
        """Test connection to UniFi Controller or UDM Pro."""
        self.ensure_one()
        try:
            client = self.get_client()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Connection successful!',
                    'type': 'success',
                },
            }
        except Exception as e:
            raise ValidationError(f"Connection failed: {e}")

    def sync_all(self):
        """Synchronize all UniFi data"""
        self.ensure_one()
        try:
            client = self.get_client()

            # Synchronize different types of data
            self.env['unifi.wifi'].sync_from_controller(client, self.id)
            self.env['unifi.network'].sync_from_controller(client, self.id)
            self.env['unifi.client'].sync_from_controller(client, self.id)
            self.env['unifi.system.health'].sync_from_controller(client, self.id)
            # Add other models sync here

            self.last_sync = fields.Datetime.now()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Synchronization completed successfully!',
                    'type': 'success',
                },
            }
        except Exception as e:
            raise UserError(f"Synchronization failed: {str(e)}")

    def action_fetch_networks_and_fill_rules(self):
        """Fetch networks and populate firewall rules."""
        self.ensure_one()
        client = self.get_client()
        try:
            networks = client.get_networks()

            firewall_rule_model = self.env['unifi.firewall.rule']
            for network in networks:
                rule_name = network.get('name')
                src_ip = network.get('subnet')
                if not src_ip:
                    continue

                firewall_rule_model.create({
                    'name': f"Network: {rule_name}",
                    'action': 'accept',
                    'enabled': True,
                    'src_ip': src_ip,
                    'dst_ip': False,
                    'log': False,
                    'controller_id': self.id,
                })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Network rules created successfully!',
                    'type': 'success',
                },
            }
        except Exception as e:
            raise UserError(f"Failed to create network rules: {str(e)}")

    def action_sync_all(self):
        """Synchronize all objects from the UniFi Controller."""
        self.ensure_one()
        try:
            self.action_sync_sites()
            self.action_sync_devices()
            self.action_sync_clients()
            self.action_sync_networks()
            self.action_sync_firewall_rules()
            self.last_sync = fields.Datetime.now()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'All objects synchronized successfully!',
                    'type': 'success',
                },
            }
        except Exception as e:
            raise UserError(f"Synchronization failed: {e}")

    def action_sync_devices(self):
        """Synchronize devices from the UniFi Controller."""
        self.ensure_one()
        try:
            _logger.info(f"Starting device sync for controller {self.name} ({self.ip_address})")
            _logger.info(f"Controller type: {self.controller_type}, Port: {self.api_port}")
            
            client = self.get_client()
            _logger.info("Successfully created API client")
            
            devices = client.list_devices()
            _logger.info(f"Retrieved {len(devices)} devices from controller")
            
            # Create or update device records
            for device in devices:
                mac = device.get('mac')
                if not mac:
                    _logger.warning("Found device without MAC address, skipping")
                    continue
                
                # Determine device type
                model = device.get('model', '')
                _logger.info(f"Processing device: MAC={mac}, Model={model}")
                
                # Prepare device values
                vals = {
                    'name': device.get('name') or device.get('model', 'Unknown Device'),
                    'mac': mac,
                    'model': model,
                    'type': 'uap' if model.startswith('U6') or model.startswith('UAP') else 'ugw' if model.startswith('UGW') or model.startswith('UXG') else 'usw' if model.startswith('USW') else 'udm' if model.startswith('UDM') else 'other',
                    'ip_address': device.get('ip'),
                    'version': device.get('version'),
                    'status': 'online' if device.get('state', 1) == 1 else 'offline',
                    'last_seen': fields.Datetime.now(),  # Current time as devices are currently connected
                    'controller_id': self.id,
                    'site_id': device.get('site_id')
                }
                
                # Find existing device or create new one
                existing_device = self.env['unifi.device'].search([
                    ('mac', '=', mac),
                    ('controller_id', '=', self.id)
                ])
                
                if existing_device:
                    existing_device.write(vals)
                    _logger.info(f"Updated device: {vals['name']} ({mac})")
                else:
                    self.env['unifi.device'].create(vals)
                    _logger.info(f"Created new device: {vals['name']} ({mac})")
            
            # Mark devices not in the response as offline
            all_devices = self.env['unifi.device'].search([('controller_id', '=', self.id)])
            current_macs = [d.get('mac') for d in devices if d.get('mac')]
            offline_devices = all_devices.filtered(lambda d: d.mac not in current_macs)
            if offline_devices:
                offline_devices.write({'status': 'offline'})
                
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': f'Successfully synchronized {len(devices)} devices!',
                    'type': 'success',
                },
            }
        except Exception as e:
            raise UserError(f"Device synchronization failed: {e}")

    def action_sync_clients(self):
        """Synchronize clients from the UniFi Controller."""
        self.ensure_one()
        try:
            client = self.get_client()
            clients = client.list_clients()
            
            # Create or update client records
            for client_data in clients:
                mac = client_data.get('mac')
                if not mac:
                    continue
                
                # Prepare client values
                vals = {
                    'name': client_data.get('name', client_data.get('hostname', 'Unknown Client')),
                    'mac': mac,
                    'last_ip': client_data.get('ip') or client_data.get('last_ip'),
                    'hostname': client_data.get('hostname'),
                    'last_seen': fields.Datetime.now(),  # Current time as clients are currently connected
                    'controller_id': self.id,
                    'site_id': client_data.get('site_id'),
                    'device_id': client_data.get('dev_id'),
                    'network_id': client_data.get('network_id'),
                    'status': 'online',
                    'is_wired': client_data.get('is_wired', False)
                }
                
                # Find existing client or create new one
                existing_client = self.env['unifi.client'].search([
                    ('mac', '=', mac),
                    ('controller_id', '=', self.id)
                ])
                
                if existing_client:
                    existing_client.write(vals)
                    _logger.info(f"Updated client: {vals['name']} ({mac})")
                else:
                    self.env['unifi.client'].create(vals)
                    _logger.info(f"Created new client: {vals['name']} ({mac})")
            
            # Mark clients not in the response as offline
            all_clients = self.env['unifi.client'].search([('controller_id', '=', self.id)])
            current_macs = [c.get('mac') for c in clients if c.get('mac')]
            offline_clients = all_clients.filtered(lambda c: c.mac not in current_macs)
            if offline_clients:
                offline_clients.write({'status': 'offline'})
                
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': f'Successfully synchronized {len(clients)} clients!',
                    'type': 'success',
                },
            }
        except Exception as e:
            raise UserError(f"Client synchronization failed: {e}")

    def action_sync_networks(self):
        """Synchronize networks from the UniFi Controller."""
        self.ensure_one()
        try:
            client = self.get_client()
            networks = client.list_networks()
            
            # Create or update network records
            for network in networks:
                network_id = network.get('_id')
                if not network_id:
                    continue
                
                # Prepare network values
                vals = {
                    'name': network.get('name', 'Unknown Network'),
                    'purpose': network.get('purpose', 'corporate'),
                    'subnet': network.get('ip_subnet'),
                    'vlan_id': network.get('vlan', ''),
                    'network_group': network.get('networkgroup', 'LAN'),
                    'dhcp_enabled': network.get('dhcp_enabled', False),
                    'dhcp_start': network.get('dhcp_start'),
                    'dhcp_stop': network.get('dhcp_stop'),
                    'domain_name': network.get('domain_name'),
                    'ctrl_id': self.id,
                    'site_id': network.get('site_id'),
                    'unifi_id': network_id
                }
                
                # Find existing network or create new one
                existing_network = self.env['unifi.network'].search([
                    ('unifi_id', '=', network_id),
                    ('ctrl_id', '=', self.id)
                ])
                
                if existing_network:
                    existing_network.write(vals)
                    _logger.info(f"Updated network: {vals['name']} ({network_id})")
                else:
                    self.env['unifi.network'].create(vals)
                    _logger.info(f"Created new network: {vals['name']} ({network_id})")
            
            # Remove networks that no longer exist
            all_networks = self.env['unifi.network'].search([('ctrl_id', '=', self.id)])
            current_ids = [n.get('_id') for n in networks if n.get('_id')]
            deleted_networks = all_networks.filtered(lambda n: n.unifi_id not in current_ids)
            if deleted_networks:
                deleted_networks.unlink()
                _logger.info(f"Removed {len(deleted_networks)} deleted networks")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': f'Successfully synchronized {len(networks)} networks!',
                    'type': 'success',
                },
            }
        except Exception as e:
            raise UserError(f"Network synchronization failed: {e}")

    def action_sync_sites(self):
        """Synchronize sites from the UniFi Controller."""
        self.ensure_one()
        try:
            client = self.get_client()
            sites = client.list_sites()
            
            # Just log the sites for now since we don't need to store them
            for site in sites:
                site_id = site.get('name')  # UniFi uses site name as ID
                if site_id:
                    _logger.info(f"Found site: {site.get('desc', site_id)} (ID: {site_id}, Role: {site.get('role', 'admin')})")
            
            _logger.info(f"Found {len(sites)} sites on controller {self.name}")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': f'Successfully found {len(sites)} sites!',
                    'type': 'success',
                },
            }
        except Exception as e:
            raise UserError(f"Site synchronization failed: {e}")

    def action_sync_firewall_rules(self):
        """Synchronize firewall rules from the UniFi Controller."""
        self.ensure_one()
        try:
            _logger.info("Synchronizing port forwarding rules from UniFi controller")
            
            # Get port forward rules from UniFi controller
            response = self.get_client().get_port_forward_rules()
            _logger.info("Port forward rules raw response: %s", response)
            
            # Extract rules from data field
            if isinstance(response, dict):
                rules = response.get('data', [])
            else:
                rules = response or []
            
            _logger.info(f"Got {len(rules)} rules from data field")
            for rule in rules:
                _logger.info(f"Processing rule: {rule}")
                _logger.info(f"Rule type: dst_port={type(rule.get('dst_port'))}, fwd={type(rule.get('fwd'))}")
                _logger.info(f"Rule values: dst_port={rule.get('dst_port')}, fwd={rule.get('fwd')}")
            
            # Get existing rules for this controller
            existing_rules = self.env['unifi.port.forward'].search([
                ('controller_id', '=', self.id)
            ])
            existing_rule_map = {r.unifi_id: r for r in existing_rules if r.unifi_id}
            
            # Create or update rules
            synced_rule_ids = []
            for rule_data in rules:
                rule_id = rule_data.get('_id')
                
                # Convert UniFi data to Odoo values
                values = self.env['unifi.port.forward'].from_unifi_dict(self.env, self, rule_data)
                
                if rule_id in existing_rule_map:
                    # Update existing rule
                    rule = existing_rule_map[rule_id]
                    rule.write(values)
                else:
                    # Create new rule
                    rule = self.env['unifi.port.forward'].create(values)
                
                synced_rule_ids.append(rule.id)
            
            # Delete rules that no longer exist on the controller
            rules_to_delete = existing_rules.filtered(lambda r: r.id not in synced_rule_ids)
            if rules_to_delete:
                rules_to_delete.unlink()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Successfully synchronized firewall rules',
                    'type': 'success'
                }
            }
            
        except Exception as e:
            _logger.error(f"Failed to sync firewall rules: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to sync firewall rules: {str(e)}',
                    'type': 'danger'
                }
            }

    def action_sync_wifi(self):
        """Synchronize WiFi networks from the UniFi Controller."""
        self.ensure_one()
        try:
            client = self.get_client()
            wifi_model = self.env['unifi.wifi']
            wifi_model.sync_from_controller(client, self.id)
            
            # Get count of synced networks
            networks_count = wifi_model.search_count([('ctrl_id', '=', self.id)])
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': f'Successfully synchronized {networks_count} WiFi networks!',
                    'type': 'success'
                }
            }
        except Exception as e:
            _logger.error(f"Failed to sync WiFi networks: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to sync WiFi networks: {str(e)}',
                    'type': 'danger'
                }
            }

    def ensure_default_firewall_groups(self):
        """Ensure default firewall groups exist in both UniFi and Odoo."""
        self.ensure_one()
        try:
            client = self.get_client()
            FirewallGroup = self.env['unifi.firewall.group']
            
            # Get existing groups from UniFi
            groups = client.get_firewall_groups()
            unifi_groups = groups.get('data', []) if groups else []
            
            # Define default groups
            defaults = [
                {
                    'name': 'Default LAN',
                    'group_type': 'address-group',
                    'members': '192.168.0.0/16\n172.16.0.0/12\n10.0.0.0/8',
                    'description': 'Default LAN networks'
                },
                {
                    'name': 'Default WAN',
                    'group_type': 'address-group',
                    'members': '0.0.0.0/0',
                    'description': 'Default WAN networks'
                }
            ]
            
            # Create or update groups
            for group_data in defaults:
                # Check if group exists in UniFi
                unifi_group = next((g for g in unifi_groups if g.get('name') == group_data['name']), None)
                
                # Create in UniFi if needed
                if not unifi_group:
                    try:
                        unifi_data = {
                            'name': group_data['name'],
                            'group_type': group_data['group_type'],
                            'group_members': [m.strip() for m in group_data['members'].split('\n') if m.strip()],
                            'group_description': group_data.get('description', '')
                        }
                        unifi_group = client.create_firewall_group(unifi_data)
                        if unifi_group:
                            unifi_group = unifi_group.get('data', {})
                    except Exception as e:
                        _logger.warning(f"Failed to create UniFi firewall group: {str(e)}")
                
                # Create or update in Odoo
                existing_group = FirewallGroup.search([
                    ('ctrl_id', '=', self.id),
                    ('name', '=', group_data['name'])
                ], limit=1)
                
                vals = {
                    'name': group_data['name'],
                    'ctrl_id': self.id,
                    'group_type': group_data['group_type'],
                    'members': group_data['members'],
                    'description': group_data.get('description', '')
                }
                
                if existing_group:
                    existing_group.write(vals)
                    _logger.info(f"Updated Odoo firewall group: {group_data['name']}")
                else:
                    FirewallGroup.create(vals)
                    _logger.info(f"Created Odoo firewall group: {group_data['name']}")
            
        except Exception as e:
            _logger.error(f"Failed to ensure default firewall groups: {str(e)}")

    @api.model
    def _sync_scheduled(self):
        """Scheduled synchronization of all controllers"""
        controllers = self.search([])
        for controller in controllers:
            if controller.should_sync():
                controller.sync_all()

    def should_sync(self):
        """Check if synchronization is needed based on interval"""
        if not self.last_sync:
            return True
        
        next_sync = self.last_sync + timedelta(minutes=self.sync_interval)
        return fields.Datetime.now() >= next_sync

    def action_sync_port_forward(self):
        """Synchronize port forwarding rules from UniFi controller."""
        self.ensure_one()
        try:
            _logger.info("Synchronizing port forwarding rules from UniFi controller")
            
            # Get port forward rules from UniFi controller
            response = self.get_client().get_port_forward_rules()
            _logger.info("Port forward rules raw response: %s", response)
            
            # Extract rules from data field
            if isinstance(response, dict):
                rules = response.get('data', [])
            else:
                rules = response or []
            
            rules_count = len(rules)
            _logger.info(f"Got {rules_count} rules from data field")
            
            # Get existing rules for this controller
            existing_rules = self.env['unifi.port.forward'].search([
                ('controller_id', '=', self.id)
            ])
            existing_rule_map = {r.unifi_id: r for r in existing_rules if r.unifi_id}
            
            # Create or update rules
            synced_rule_ids = []
            for rule_data in rules:
                rule_id = rule_data.get('_id')
                
                # Convert UniFi data to Odoo values
                values = self.env['unifi.port.forward'].from_unifi_dict(self.env, self, rule_data)
                
                if rule_id in existing_rule_map:
                    # Update existing rule
                    rule = existing_rule_map[rule_id]
                    rule.write(values)
                else:
                    # Create new rule
                    rule = self.env['unifi.port.forward'].create(values)
                
                synced_rule_ids.append(rule.id)
            
            # Delete rules that no longer exist on the controller
            rules_to_delete = existing_rules.filtered(lambda r: r.id not in synced_rule_ids)
            if rules_to_delete:
                rules_to_delete.unlink()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('{} port forwarding rules synchronized successfully').format(rules_count),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error(f"Failed to sync port forwarding rules: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Failed to sync port forwarding rules: {}').format(str(e)),
                    'type': 'danger'
                }
            }

    @api.depends('last_sync')
    def _compute_dashboard_data(self):
        """Compute all dashboard metrics."""
        for controller in self:
            try:
                client = controller.get_client()
                
                # Get clients data
                clients = client.list_clients()
                devices = client.list_devices()
                
                # Basic metrics
                controller.total_clients = len(clients)
                controller.active_clients = len([c for c in clients if c.get('status') == 'online'])
                controller.total_devices = len(devices)
                controller.offline_devices = len([d for d in devices if not d.get('state', True)])
                
                # Bandwidth calculations
                wan_stats = client._api_request('GET', f'api/s/{client.site_id}/stat/sta')
                total_rx = sum(stat.get('rx_bytes', 0) for stat in wan_stats.get('data', []))
                total_tx = sum(stat.get('tx_bytes', 0) for stat in wan_stats.get('data', []))
                controller.total_bandwidth = (total_rx + total_tx) / (1024 * 1024)  # Convert to Mbps
                controller.bandwidth_usage = min(100, (controller.total_bandwidth / 1000) * 100)  # Assuming 1Gbps capacity
                
                # Client type chart data
                wired_clients = len([c for c in clients if c.get('is_wired')])
                wireless_clients = len(clients) - wired_clients
                controller.client_type_chart = {
                    'labels': ['Filaire', 'Sans Fil'],
                    'datasets': [{
                        'data': [wired_clients, wireless_clients],
                        'backgroundColor': ['#36A2EB', '#FF6384']
                    }]
                }
                
                # Bandwidth chart data (last 24h)
                bandwidth_stats = client._api_request('GET', f'api/s/{client.site_id}/stat/report/hourly.site')
                controller.bandwidth_chart = {
                    'labels': [stat.get('time') for stat in bandwidth_stats.get('data', [])[-24:]],
                    'datasets': [{
                        'label': 'Download',
                        'data': [stat.get('rx_bytes', 0) / (1024 * 1024) for stat in bandwidth_stats.get('data', [])[-24:]],
                        'borderColor': '#36A2EB'
                    }, {
                        'label': 'Upload',
                        'data': [stat.get('tx_bytes', 0) / (1024 * 1024) for stat in bandwidth_stats.get('data', [])[-24:]],
                        'borderColor': '#FF6384'
                    }]
                }
                
                # Security metrics
                firewall_rules = client.get_firewall_rules()
                controller.active_firewall_rules = len([r for r in firewall_rules.get('data', []) if r.get('enabled')])
                
                events = client._api_request('GET', f'api/s/{client.site_id}/stat/event')
                controller.blocked_connections = len([e for e in events.get('data', []) 
                    if e.get('key') == 'EVT_FW_Blocked'])
                
                threats = client._api_request('GET', f'api/s/{client.site_id}/stat/ips/event')
                controller.threat_count = len(threats.get('data', []))
                
                # Alerts
                system_health = client._api_request('GET', f'api/s/{client.site_id}/stat/health')
                alerts = [h for h in system_health.get('data', []) if h.get('severity', 'info') != 'info']
                controller.active_alerts = len(alerts)
                controller.critical_alerts = len([a for a in alerts if a.get('severity') == 'critical'])
                
                # VPN Status
                vpn_status = client._api_request('GET', f'api/s/{client.site_id}/stat/vpn')
                active_vpns = [v for v in vpn_status.get('data', []) if v.get('status') == 'up']
                if len(active_vpns) == len(vpn_status.get('data', [])):
                    controller.vpn_status = 'up'
                elif len(active_vpns) == 0:
                    controller.vpn_status = 'down'
                else:
                    controller.vpn_status = 'partial'
                
            except Exception as e:
                _logger.error(f"Error computing dashboard data: {str(e)}")
                # Set default values in case of error
                controller.total_clients = 0
                controller.active_clients = 0
                controller.total_devices = 0
                controller.offline_devices = 0
                controller.total_bandwidth = 0
                controller.bandwidth_usage = 0
                controller.active_alerts = 0
                controller.critical_alerts = 0
                controller.client_type_chart = {'labels': [], 'datasets': [{'data': []}]}
                controller.bandwidth_chart = {'labels': [], 'datasets': []}
                controller.active_firewall_rules = 0
                controller.blocked_connections = 0
                controller.vpn_status = 'down'
                controller.threat_count = 0
