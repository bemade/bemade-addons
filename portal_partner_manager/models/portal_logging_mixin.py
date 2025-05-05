#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class PortalActivityLog(models.Model):
    _name = 'portal.activity.log'
    _description = 'Portal Activity Log'
    _order = 'create_date desc'
    
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        readonly=True,
        index=True
    )
    
    ip = fields.Char(
        string='IP Address',
        readonly=True,
        help="IP address of the user performing the action"
    )
    
    model = fields.Char(
        string='Model',
        required=True,
        readonly=True,
        index=True
    )
    
    res_id = fields.Integer(
        string='Resource ID',
        required=True,
        readonly=True,
        index=True
    )
    
    action = fields.Selection([
        ('view', 'View'),
        ('edit', 'Edit'),
        ('edit_user', 'Edit User'),
        ('create', 'Create'),
        ('archive', 'Archive'),
        ('unarchive', 'Unarchive'),
        ('grant_access', 'Grant Access'),
        ('revoke_access', 'Revoke Access'),
        ('other', 'Other')
    ], string='Action', required=True, readonly=True)
    
    details = fields.Text(
        string='Details',
        readonly=True
    )
    
    create_date = fields.Datetime(
        string='Date',
        readonly=True
    )
    
    resource_name = fields.Char(
        string='Resource Name',
        compute='_compute_resource_name',
        store=True
    )
    
    @api.depends('model', 'res_id')
    def _compute_resource_name(self):
        """Calcule le nom du modèle associé à chaque log"""
        for log in self:
            if log.model and log.res_id:
                record = self.env[log.model].sudo().browse(log.res_id).exists()
                if record:
                    log.resource_name = record.display_name
                else:
                    log.resource_name = f"{log.model},{log.res_id} (Deleted)"
            else:
                log.resource_name = False


class PortalLoggingMixin(models.AbstractModel):
    _name = 'portal.logging.mixin'
    _description = 'Portal Activity Logging Mixin'
    
    log_ids = fields.One2many(
        'portal.activity.log',
        'res_id',
        string="Activity Logs",
        domain=lambda self: [('model', '=', self._name)],
        readonly=True
    )
    
    def log_portal_activity(self, user_id, action, details=None, ip=None):
        """
        Records a portal activity in the log
        
        :param user_id: ID of the user performing the action
        :param action: Type of action performed (view, edit, create, etc.)
        :param details: Optional details about the action
        :param ip: IP address of the user performing the action
        :return: Created log entry
        """
        self.ensure_one()
        
        # L'adresse IP doit être passée depuis le contrôleur
        # car request n'est pas directement accessible depuis les modèles
        
        return self.env['portal.activity.log'].create({
            'user_id': user_id,
            'model': self._name,
            'res_id': self.id,
            'action': action,
            'details': details or '',
            'ip': ip or False,
        })
