"""UniFi Client Device Model for Odoo."""
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime

class UnifiClient(models.Model):
    """UniFi Client Device Model."""
    _name = 'unifi.client'
    _description = 'UniFi Client Device'
    _rec_name = 'display_name'

    name = fields.Char(
        string='Name',
        required=True,
        help="Client device name or hostname"
    )

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        help="Human-readable device name"
    )

    mac = fields.Char(
        string='MAC Address',
        required=True,
        help="MAC address of the client device"
    )

    last_ip = fields.Char(
        string='IP Address',
        help="Current IP address of the client device"
    )

    hostname = fields.Char(
        string='Hostname',
        help="Device hostname"
    )

    oui = fields.Char(
        string='Manufacturer',
        help="Device manufacturer based on OUI"
    )

    device_name = fields.Char(
        string='Device Model',
        help="Device model name"
    )

    controller_id = fields.Many2one(
        'unifi.ctrl',
        string='Controller',
        required=True,
        help="UniFi controller managing this client"
    )

    is_wired = fields.Boolean(
        string='Wired Connection',
        default=False,
        help="Whether this client is connected via ethernet"
    )

    is_guest = fields.Boolean(
        string='Guest Network',
        default=False,
        help="Whether this client is on a guest network"
    )

    network = fields.Char(
        string='Network',
        help="Network name the client is connected to"
    )

    essid = fields.Char(
        string='SSID',
        help="Wireless network SSID"
    )

    last_seen = fields.Datetime(
        string='Last Seen',
        help="Last time this client was seen on the network"
    )

    uptime = fields.Integer(
        string='Uptime',
        help="Client uptime in seconds"
    )

    tx_bytes = fields.Float(
        string='TX Bytes',
        help="Total bytes transmitted"
    )

    rx_bytes = fields.Float(
        string='RX Bytes',
        help="Total bytes received"
    )

    satisfaction = fields.Integer(
        string='Satisfaction',
        help="Client satisfaction score (0-100)"
    )

    signal = fields.Integer(
        string='Signal Strength',
        help="Signal strength in dBm"
    )

    noise = fields.Integer(
        string='Noise Floor',
        help="Noise floor in dBm"
    )

    tx_rate = fields.Integer(
        string='TX Rate',
        help="Transmit rate in Kbps"
    )

    rx_rate = fields.Integer(
        string='RX Rate',
        help="Receive rate in Kbps"
    )

    # Device categorization fields
    dev_cat = fields.Integer(
        string='Device Category',
        help="UniFi device category identifier"
    )

    dev_family = fields.Integer(
        string='Device Family',
        help="UniFi device family identifier"
    )

    dev_vendor = fields.Integer(
        string='Device Vendor',
        help="UniFi device vendor identifier"
    )

    os_name = fields.Integer(
        string='Operating System',
        help="UniFi operating system identifier"
    )

    # Wireless connection details
    channel = fields.Integer(
        string='Channel',
        help="WiFi channel number"
    )

    radio = fields.Char(
        string='Radio',
        help="Radio type (ng/na)"
    )

    radio_proto = fields.Char(
        string='Radio Protocol',
        help="Radio protocol (g/ac/ax)"
    )

    channel_width = fields.Integer(
        string='Channel Width',
        help="Channel width in MHz"
    )

    bssid = fields.Char(
        string='BSSID',
        help="Connected access point BSSID"
    )

    ap_mac = fields.Char(
        string='AP MAC',
        help="Connected access point MAC address"
    )

    # Performance metrics
    tx_retries = fields.Integer(
        string='TX Retries',
        help="Number of transmission retries"
    )

    wifi_tx_attempts = fields.Integer(
        string='TX Attempts',
        help="Total transmission attempts"
    )

    wifi_tx_dropped = fields.Integer(
        string='TX Dropped',
        help="Number of dropped transmissions"
    )

    tx_retries_percentage = fields.Float(
        string='TX Retry Rate',
        help="Transmission retry rate percentage"
    )

    bytes_r = fields.Float(
        string='Transfer Rate',
        help="Current transfer rate in bytes/sec"
    )

    site_id = fields.Char(
        string='Site ID',
        help="UniFi site identifier"
    )

    device_id = fields.Integer(
        string='Device ID',
        help="UniFi device identifier"
    )

    network_id = fields.Char(
        string='Network ID',
        help="UniFi network identifier"
    )

    status = fields.Selection(
        [
            ('online', 'Online'),
            ('offline', 'Offline')
        ],
        string='Status',
        default='offline',
        help="Client connection status"
    )

    _sql_constraints = [
        ('unique_mac_controller', 'unique(mac,controller_id)', 
         'A client with this MAC address already exists for this controller!')
    ]

    @api.depends('name', 'hostname', 'device_name', 'mac')
    def _compute_display_name(self):
        """Compute a human-readable display name."""
        for client in self:
            if client.device_name and client.hostname:
                client.display_name = f"{client.hostname} ({client.device_name})"
            elif client.hostname:
                client.display_name = client.hostname
            elif client.device_name:
                client.display_name = client.device_name
            elif client.name:
                client.display_name = client.name
            else:
                client.display_name = client.mac

    @api.model
    def sync_from_controller(self, client, controller_id):
        """Synchronize clients from UniFi controller."""
        try:
            # Get all clients from the controller
            clients_data = client.list_clients()
            
            for client_data in clients_data:
                vals = {
                    'name': client_data.get('hostname') or client_data.get('device_name') or client_data.get('mac'),
                    'mac': client_data.get('mac'),
                    'last_ip': client_data.get('last_ip') or client_data.get('ip'),
                    'hostname': client_data.get('hostname'),
                    'oui': client_data.get('oui'),
                    'device_name': client_data.get('device_name'),
                    'controller_id': controller_id,
                    'is_wired': bool(client_data.get('is_wired')),
                    'is_guest': bool(client_data.get('is_guest')),
                    'network': client_data.get('network'),
                    'essid': client_data.get('essid'),
                    'last_seen': datetime.fromtimestamp(client_data.get('last_seen', 0)),
                    'uptime': client_data.get('uptime', 0),
                    'tx_bytes': float(client_data.get('tx_bytes', 0)),
                    'rx_bytes': float(client_data.get('rx_bytes', 0)),
                    'satisfaction': client_data.get('satisfaction', 0),
                    'signal': client_data.get('signal', 0),
                    'noise': client_data.get('noise', 0),
                    'tx_rate': client_data.get('tx_rate', 0),
                    'rx_rate': client_data.get('rx_rate', 0),
                    # Device categorization
                    'dev_cat': client_data.get('dev_cat'),
                    'dev_family': client_data.get('dev_family'),
                    'dev_vendor': client_data.get('dev_vendor'),
                    'os_name': client_data.get('os_name'),
                    # Wireless details
                    'channel': client_data.get('channel'),
                    'radio': client_data.get('radio'),
                    'radio_proto': client_data.get('radio_proto'),
                    'channel_width': client_data.get('channel_width'),
                    'bssid': client_data.get('bssid'),
                    'ap_mac': client_data.get('ap_mac'),
                    # Performance metrics
                    'tx_retries': client_data.get('tx_retries', 0),
                    'wifi_tx_attempts': client_data.get('wifi_tx_attempts', 0),
                    'wifi_tx_dropped': client_data.get('wifi_tx_dropped', 0),
                    'tx_retries_percentage': client_data.get('tx_retries_percentage', 0.0),
                    'bytes_r': client_data.get('bytes-r', 0.0),
                    'site_id': client_data.get('site_id'),
                    'device_id': client_data.get('dev_id'),
                    'network_id': client_data.get('network_id'),
                    'status': 'online' if client_data.get('last_seen') else 'offline',
                }
                
                # Try to find existing client
                existing = self.search([
                    ('mac', '=', vals['mac']),
                    ('controller_id', '=', vals['controller_id'])
                ])
                
                if existing:
                    existing.write(vals)
                else:
                    self.create(vals)
                    
        except Exception as e:
            raise UserError(f"Failed to sync clients: {str(e)}")
