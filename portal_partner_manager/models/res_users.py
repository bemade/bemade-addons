#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class Users(models.Model):
    _name = 'res.users'
    _inherit = 'res.users'
    _description = "Users with Portal Logging"
    
    # Ajouter les champs du mixin manuellement pour éviter les problèmes avec l'authentification
    log_ids = fields.One2many(
        'portal.activity.log',
        'res_id',
        string="Activity Logs",
        domain=lambda self: [('model', '=', self._name)],
        readonly=True
    )
    
    # Nous n'avons pas besoin de redéfinir onchange car nous héritons correctement
    
    # Vous pouvez ajouter ici des champs ou méthodes spécifiques aux utilisateurs
    # liés à la fonctionnalité de journalisation
    
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
        
        return self.env['portal.activity.log'].create({
            'user_id': user_id,
            'model': self._name,
            'res_id': self.id,
            'action': action,
            'details': details or '',
            'ip': ip or False,
        })
    
    def write(self, vals):
        """
        Surcharge de write pour journaliser automatiquement les modifications
        effectuées via le portail
        """
        res = super(Users, self).write(vals)
        
        # Si l'utilisateur est un utilisateur du portail et modifie son propre profil
        portal_user = self.env.user
        if portal_user.has_group('base.group_portal') and portal_user.id in self.ids:
            # Créer un log d'activité détaillé
            details = ", ".join([f"{key}: {vals[key]}" for key in vals if key not in ['__last_update', 'write_date']])
            if details:
                self.filtered(lambda u: u.id == portal_user.id).log_portal_activity(
                    user_id=portal_user.id,
                    action='edit',
                    details=f"User updated profile: {details}"
                )
        
        return res
        
    @api.model_create_multi
    def create(self, vals_list):
        """
        Surcharge de create pour journaliser la création d'utilisateurs du portail
        """
        users = super(Users, self).create(vals_list)
        
        # Journaliser uniquement si l'utilisateur créateur est un utilisateur du portail
        portal_user = self.env.user
        if portal_user.has_group('base.group_portal'):
            for user in users:
                if user.has_group('base.group_portal'):
                    user.log_portal_activity(
                        user_id=portal_user.id,
                        action='create',
                        details=f"Portal user created: {user.name} ({user.login})"
                    )
        
        return users
