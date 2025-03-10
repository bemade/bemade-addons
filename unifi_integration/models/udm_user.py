# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UdmUser(models.Model):
    """Représentation d'un utilisateur dans l'UDM Pro"""
    _name = 'udm.user'
    _description = 'UDM Pro User'
    
    config_id = fields.Many2one('udm.configuration', string='Configuration', ondelete='cascade')
    name = fields.Char(string='Name', required=True)
    email = fields.Char(string='Email')
    role = fields.Char(string='Role')
    enabled = fields.Boolean(string='Enabled', default=True)
    raw_data = fields.Text(string='Raw Data')
    
    # Champs calculés pour des statistiques ou filtrage
    is_admin = fields.Boolean(string='Is Admin', compute='_compute_is_admin', store=True)
    
    @api.depends('role')
    def _compute_is_admin(self):
        for record in self:
            record.is_admin = record.role and 'admin' in record.role.lower() or False
