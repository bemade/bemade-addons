from odoo import models, fields, api

class ProxmoxVM(models.Model):
    _name = 'proxmox.vm'
    _description = 'Proxmox Virtual Machine'
    _order = 'name'
    _inherit = ['mail.thread']

    name = fields.Char(string='Name', required=True, tracking=True)
    vmid = fields.Integer(string='VM ID', required=True, tracking=True)
    server_id = fields.Many2one('proxmox.server', string='Server', required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, 
                                related='server_id.company_id', store=True, readonly=True)
    status = fields.Selection([
        ('running', 'Running'),
        ('stopped', 'Stopped'),
        ('suspended', 'Suspended')
    ], string='Status', default='stopped', tracking=True)
    memory = fields.Integer(string='Memory (MB)')
    cpus = fields.Integer(string='vCPUs')
    disk_size = fields.Float(string='Disk Size (GB)')
    ip_address = fields.Char(string='IP Address')

    def action_start(self):
        """Start the virtual machine"""
        self.ensure_one()
        proxmox = self.server_id._get_proxmox_connection()
        if proxmox:
            try:
                proxmox.nodes(self.server_id.hostname).qemu(self.vmid).status.start.post()
                self.status = 'running'
                return True
            except Exception as e:
                return False
        return False

    def action_stop(self):
        """Stop the virtual machine"""
        self.ensure_one()
        proxmox = self.server_id._get_proxmox_connection()
        if proxmox:
            try:
                proxmox.nodes(self.server_id.hostname).qemu(self.vmid).status.stop.post()
                self.status = 'stopped'
                return True
            except Exception as e:
                return False
        return False

    def action_restart(self):
        """Restart the virtual machine"""
        self.ensure_one()
        proxmox = self.server_id._get_proxmox_connection()
        if proxmox:
            try:
                proxmox.nodes(self.server_id.hostname).qemu(self.vmid).status.reset.post()
                self.status = 'running'
                return True
            except Exception as e:
                return False
        return False

    def action_suspend(self):
        """Suspend the virtual machine"""
        self.ensure_one()
        proxmox = self.server_id._get_proxmox_connection()
        if proxmox:
            try:
                proxmox.nodes(self.server_id.hostname).qemu(self.vmid).status.suspend.post()
                self.status = 'suspended'
                return True
            except Exception as e:
                return False
        return False

    def action_resume(self):
        """Resume the virtual machine"""
        self.ensure_one()
        proxmox = self.server_id._get_proxmox_connection()
        if proxmox:
            try:
                proxmox.nodes(self.server_id.hostname).qemu(self.vmid).status.resume.post()
                self.status = 'running'
                return True
            except Exception as e:
                return False
        return False
