# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, timedelta

class PlanningRequest(models.Model):
    """Modèle pour les demandes de planning créées par les utilisateurs du portail."""
    _name = 'portal.planning.request'
    _description = 'Planning Request'
    _rec_name = 'name'
    _order = 'start_datetime desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Titre', required=True, tracking=True)
    description = fields.Text(string='Description', tracking=True)
    employee_id = fields.Many2one('hr.employee', string='Employé', required=True, default=lambda self: self.env.user.employee_id.id, tracking=True)
    user_id = fields.Many2one('res.users', string='Utilisateur', related='employee_id.user_id', store=True)
    role_id = fields.Many2one('planning.role', string='Rôle', tracking=True)
    start_datetime = fields.Datetime(string='Date de début', required=True, tracking=True)
    end_datetime = fields.Datetime(string='Date de fin', required=True, tracking=True)
    allocated_hours = fields.Float(string='Durée', compute='_compute_allocated_hours', store=True, readonly=False, tracking=True)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('submitted', 'Soumis'),
        ('approved', 'Approuvé'),
        ('rejected', 'Refusé'),
        ('cancelled', 'Annulé'),
    ], string='État', default='draft', tracking=True, copy=False)
    company_id = fields.Many2one('res.company', string='Société', default=lambda self: self.env.company)
    planning_slot_id = fields.Many2one('planning.slot', string='Créneau de planning créé', readonly=True, copy=False)
    can_edit = fields.Boolean(compute='_compute_can_edit')
    can_submit = fields.Boolean(compute='_compute_can_submit')
    can_approve = fields.Boolean(compute='_compute_can_approve')
    can_reject = fields.Boolean(compute='_compute_can_reject')
    can_cancel = fields.Boolean(compute='_compute_can_cancel')
    
    @api.depends('start_datetime', 'end_datetime')
    def _compute_allocated_hours(self):
        for request in self:
            if request.start_datetime and request.end_datetime:
                delta = request.end_datetime - request.start_datetime
                request.allocated_hours = delta.total_seconds() / 3600
            else:
                request.allocated_hours = 0
    
    @api.depends('state', 'user_id')
    def _compute_can_edit(self):
        for request in self:
            request.can_edit = request.state == 'draft' and request.user_id.id == self.env.user.id
    
    @api.depends('state', 'user_id')
    def _compute_can_submit(self):
        for request in self:
            request.can_submit = request.state == 'draft' and request.user_id.id == self.env.user.id
    
    @api.depends('state')
    def _compute_can_approve(self):
        is_manager = self.env.user.has_group('planning.group_planning_manager')
        for request in self:
            request.can_approve = request.state == 'submitted' and is_manager
    
    @api.depends('state')
    def _compute_can_reject(self):
        is_manager = self.env.user.has_group('planning.group_planning_manager')
        for request in self:
            request.can_reject = request.state == 'submitted' and is_manager
    
    @api.depends('state', 'user_id')
    def _compute_can_cancel(self):
        is_manager = self.env.user.has_group('planning.group_planning_manager')
        for request in self:
            request.can_cancel = (request.state in ['draft', 'submitted'] and request.user_id.id == self.env.user.id) or \
                               (request.state in ['submitted', 'approved'] and is_manager)
    
    def action_submit(self):
        self.ensure_one()
        if self.can_submit:
            self.write({'state': 'submitted'})
            # Envoyer une notification au responsable
            self.message_post(
                body=_('Demande de planning soumise par %s') % self.employee_id.name,
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )
        return True
    
    def action_approve(self):
        self.ensure_one()
        if self.can_approve:
            # Créer un créneau de planning réel
            slot_vals = {
                'employee_id': self.employee_id.id,
                'role_id': self.role_id.id,
                'start_datetime': self.start_datetime,
                'end_datetime': self.end_datetime,
                'allocated_hours': self.allocated_hours,
                'name': self.description,
                'state': 'published',
            }
            slot = self.env['planning.slot'].sudo().create(slot_vals)
            
            # Mettre à jour la demande
            self.write({
                'state': 'approved',
                'planning_slot_id': slot.id
            })
            
            # Envoyer une notification à l'employé
            self.message_post(
                body=_('Demande de planning approuvée. Un créneau de planning a été créé.'),
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )
        return True
    
    def action_reject(self):
        self.ensure_one()
        if self.can_reject:
            self.write({'state': 'rejected'})
            # Envoyer une notification à l'employé
            self.message_post(
                body=_('Demande de planning refusée.'),
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )
        return True
    
    def action_cancel(self):
        self.ensure_one()
        if self.can_cancel:
            self.write({'state': 'cancelled'})
            # Envoyer une notification
            self.message_post(
                body=_('Demande de planning annulée.'),
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )
        return True
    
    def action_reset_to_draft(self):
        self.ensure_one()
        if self.state in ['rejected', 'cancelled'] and self.user_id.id == self.env.user.id:
            self.write({'state': 'draft'})
        return True
    
    @api.model
    def _sync_planning_slots(self):
        """Synchronise les créneaux de planning avec les demandes approuvées."""
        # Cette méthode peut être utilisée pour synchroniser les demandes approuvées
        # avec les créneaux de planning existants si nécessaire
        return True
    
    def action_view_planning_slot(self):
        """Afficher le créneau de planning associé à cette demande."""
        self.ensure_one()
        if not self.planning_slot_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Information'),
                    'message': _('Aucun créneau de planning n\'est associé à cette demande.'),
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        return {
            'name': _('Créneau de planning'),
            'type': 'ir.actions.act_window',
            'res_model': 'planning.slot',
            'res_id': self.planning_slot_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
