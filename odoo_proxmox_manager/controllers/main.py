from odoo import http
from odoo.http import request

class ProxmoxController(http.Controller):
    
    @http.route('/proxmox/dashboard/data', type='json', auth='user')
    def get_dashboard_data(self):
        """Get dashboard data for the Proxmox overview"""
        return request.env['proxmox.server'].get_dashboard_data()
