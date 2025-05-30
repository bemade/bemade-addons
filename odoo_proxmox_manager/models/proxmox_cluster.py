from odoo import models, fields, api

class ProxmoxCluster(models.Model):
    _name = 'proxmox.cluster'
    _description = 'Proxmox Cluster'
    _order = 'name'
    _inherit = ['mail.thread']

    name = fields.Char(string='Name', required=True, tracking=True)
    description = fields.Text(string='Description', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    server_ids = fields.One2many('proxmox.server', 'cluster_id', string='Servers')
    server_count = fields.Integer(string='Server Count', compute='_compute_server_count')
    total_vms = fields.Integer(string='Total VMs', compute='_compute_total_vms')
    active_servers = fields.Integer(string='Active Servers', compute='_compute_active_servers')

    @api.depends('server_ids')
    def _compute_server_count(self):
        for cluster in self:
            cluster.server_count = len(cluster.server_ids)

    @api.depends('server_ids.vm_ids')
    def _compute_total_vms(self):
        for cluster in self:
            cluster.total_vms = sum(server.vm_count for server in cluster.server_ids)

    @api.depends('server_ids.state')
    def _compute_active_servers(self):
        for cluster in self:
            cluster.active_servers = len(cluster.server_ids.filtered(lambda s: s.state == 'online'))

    def action_sync_all_servers(self):
        """Synchronize all servers in the cluster"""
        self.ensure_one()
        for server in self.server_ids:
            server.action_sync_vms()
        return True
