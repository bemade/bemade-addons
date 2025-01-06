"""UniFi System Health Model."""

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime

class UnifiSystemHealth(models.Model):
    """System health statistics from UniFi Controller."""
    _name = 'unifi.system.health'
    _description = 'UniFi System Health'

    subsystem = fields.Char(string='Subsystem', required=True)
    status = fields.Selection([
        ('ok', 'OK'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ], string='Status', required=True)
    num_user = fields.Integer(string='Number of Users')
    num_guest = fields.Integer(string='Number of Guests')
    lan_throughput = fields.Float(string='LAN Throughput (bytes/s)')
    wlan_throughput = fields.Float(string='WLAN Throughput (bytes/s)')
    wan_throughput = fields.Float(string='WAN Throughput (bytes/s)')
    cpu_usage = fields.Float(string='CPU Usage (%)')
    mem_usage = fields.Float(string='Memory Usage (%)')
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now)
    
    ctrl_id = fields.Many2one(
        'unifi.ctrl', 
        string='Controller', 
        required=True, 
        help="Controller where this data is from."
    )

    @api.model
    def sync_from_controller(self, client, controller_id):
        """Synchronize system health from UniFi Controller."""
        health_data = client.get_system_health()
        
        for data in health_data:
            vals = {
                'subsystem': data.get('subsystem', ''),
                'status': data.get('status', 'error').lower(),
                'num_user': data.get('num_user', 0),
                'num_guest': data.get('num_guest', 0),
                'lan_throughput': data.get('lan_throughput', 0.0),
                'wlan_throughput': data.get('wlan_throughput', 0.0),
                'wan_throughput': data.get('wan_throughput', 0.0),
                'cpu_usage': data.get('cpu_usage', 0.0),
                'mem_usage': data.get('mem_usage', 0.0),
                'timestamp': fields.Datetime.now(),
                'ctrl_id': controller_id,
            }
            # Create new record each time as this is time-series data
            self.create(vals)
