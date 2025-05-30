from odoo import models, fields, api
from proxmoxer import ProxmoxAPI
import requests
import logging

_logger = logging.getLogger(__name__)

class ProxmoxServer(models.Model):
    _name = 'proxmox.server'
    _description = 'Proxmox Server'
    _order = 'name'
    _inherit = ['mail.thread']

    name = fields.Char(string='Name', required=True, tracking=True)
    hostname = fields.Char(string='Hostname', required=True, tracking=True)
    port = fields.Integer(string='Port', default=8006, tracking=True)
    cluster_id = fields.Many2one('proxmox.cluster', string='Cluster', tracking=True)
    username = fields.Char(string='Username', required=True, tracking=True)
    token_name = fields.Char(string='API Token Name', tracking=True)
    token_value = fields.Char(string='API Token Value', tracking=True)
    verify_ssl = fields.Boolean(string='Verify SSL', default=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('offline', 'Offline'),
        ('online', 'Online')
    ], string='Status', default='offline', compute='_compute_state', store=True, tracking=True)
    vm_ids = fields.One2many('proxmox.vm', 'server_id', string='Virtual Machines')
    vm_count = fields.Integer(string='VM Count', compute='_compute_vm_count')
    node_info = fields.Text(string='Node Information', compute='_compute_node_info')

    def _get_proxmox_connection(self):
        try:
            if not self.token_name or not self.token_value:
                raise ValueError("API Token is required")
            
            return ProxmoxAPI(
                self.hostname,
                port=self.port,
                user=self.username,
                token_name=self.token_name,
                token_value=self.token_value,
                verify_ssl=self.verify_ssl
            )
        except Exception as e:
            _logger.error(f"Failed to connect to Proxmox server {self.name}: {str(e)}")
            return None

    @api.depends('hostname', 'port', 'token_name', 'token_value')
    def _compute_state(self):
        for server in self:
            try:
                proxmox = server._get_proxmox_connection()
                if proxmox:
                    # Test connection by getting version info
                    proxmox.version.get()
                    server.state = 'online'
                else:
                    server.state = 'offline'
            except:
                server.state = 'offline'

    @api.depends('vm_ids')
    def _compute_vm_count(self):
        for server in self:
            server.vm_count = len(server.vm_ids)

    def _compute_node_info(self):
        for server in self:
            try:
                proxmox = server._get_proxmox_connection()
                if proxmox:
                    node_info = proxmox.nodes(server.hostname).status.get()
                    server.node_info = str(node_info)
                else:
                    server.node_info = "Unable to connect to server"
            except Exception as e:
                server.node_info = f"Error getting node info: {str(e)}"

    def action_sync_vms(self):
        """Synchronize VMs from Proxmox server"""
        self.ensure_one()
        proxmox = self._get_proxmox_connection()
        if not proxmox:
            return False

        try:
            # Get all VMs from the server
            vms = proxmox.nodes(self.hostname).qemu.get()
            
            # Update or create VM records
            for vm in vms:
                vm_vals = {
                    'name': vm.get('name'),
                    'vmid': vm.get('vmid'),
                    'status': vm.get('status'),
                    'server_id': self.id,
                }
                existing_vm = self.env['proxmox.vm'].search([
                    ('server_id', '=', self.id),
                    ('vmid', '=', vm.get('vmid'))
                ])
                if existing_vm:
                    existing_vm.write(vm_vals)
                else:
                    self.env['proxmox.vm'].create(vm_vals)

            return True
        except Exception as e:
            _logger.error(f"Failed to sync VMs for server {self.name}: {str(e)}")
            return False

    @api.model
    def get_dashboard_data(self):
        """Get dashboard data for the Proxmox overview"""
        servers = self.search([])
        clusters = self.env['proxmox.cluster'].search([])
        vms = self.env['proxmox.vm'].search([])

        server_data = []
        for server in servers:
            try:
                proxmox = server._get_proxmox_connection()
                if proxmox:
                    node_info = proxmox.nodes(server.hostname).status.get()
                    memory_total = node_info.get('memory', {}).get('total', 0)
                    memory_used = node_info.get('memory', {}).get('used', 0)
                    memory_usage = round((memory_used / memory_total) * 100, 2) if memory_total else 0
                    
                    cpu_usage = round(node_info.get('cpu', 0) * 100, 2)
                    
                    server_data.append({
                        'id': server.id,
                        'name': server.name,
                        'state': server.state,
                        'vm_count': server.vm_count,
                        'memory_usage': memory_usage,
                        'cpu_usage': cpu_usage,
                    })
                else:
                    server_data.append({
                        'id': server.id,
                        'name': server.name,
                        'state': 'offline',
                        'vm_count': server.vm_count,
                        'memory_usage': 0,
                        'cpu_usage': 0,
                    })
            except Exception as e:
                _logger.error(f"Error getting data for server {server.name}: {str(e)}")
                server_data.append({
                    'id': server.id,
                    'name': server.name,
                    'state': 'offline',
                    'vm_count': server.vm_count,
                    'memory_usage': 0,
                    'cpu_usage': 0,
                })

        return {
            'server_count': len(servers),
            'cluster_count': len(clusters),
            'vm_count': len(vms),
            'servers': server_data,
        }
