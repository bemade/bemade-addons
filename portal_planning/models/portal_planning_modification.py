# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, timedelta

class PlanningModification(models.Model):
    """Modèle pour suivre les modifications de créneaux de planning via le portail."""
    _name = 'portal.planning.modification'
    _description = 'Modification de Planning via Portail'
    _rec_name = 'slot_id'
    _order = 'date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    slot_id = fields.Many2one(
        'planning.slot',
        string='Créneau de planning',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    user_id = fields.Many2one(
        'res.users',
        string='Demandé par',
        required=True,
        default=lambda self: self.env.user.id,
        tracking=True
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employé',
        related='slot_id.employee_id',
        store=True,
        readonly=True
    )
    date = fields.Datetime(
        string='Date de demande',
        required=True,
        default=fields.Datetime.now,
        tracking=True
    )
    
    # Valeurs originales
    old_start = fields.Datetime(
        string='Début original',
        required=True,
        tracking=True
    )
    old_end = fields.Datetime(
        string='Fin originale',
        required=True,
        tracking=True
    )
    old_role_id = fields.Many2one(
        'planning.role',
        string='Rôle original',
        tracking=True
    )
    
    # Nouvelles valeurs
    new_start = fields.Datetime(
        string='Nouveau début',
        required=True,
        tracking=True
    )
    new_end = fields.Datetime(
        string='Nouvelle fin',
        required=True,
        tracking=True
    )
    new_role_id = fields.Many2one(
        'planning.role',
        string='Nouveau rôle',
        tracking=True
    )
    
    # Suivi de la demande
    state = fields.Selection([
        ('pending', 'En attente'),
        ('approved', 'Approuvé'),
        ('rejected', 'Refusé'),
        ('cancelled', 'Annulé')
    ], string='État', default='pending', tracking=True, copy=False)
    approver_id = fields.Many2one(
        'res.users',
        string='Approuvé/Refusé par',
        copy=False,
        tracking=True
    )
    approval_date = fields.Datetime(
        string='Date d\'approbation/refus',
        copy=False,
        tracking=True
    )
    notes = fields.Text(
        string='Notes',
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company
    )
    
    # Champs calculés
    allocated_hours = fields.Float(
        string='Heures allouées',
        compute='_compute_allocated_hours',
        store=True,
        readonly=True
    )
    can_approve = fields.Boolean(
        compute='_compute_can_approve',
        string='Peut approuver',
        help="Indique si l'utilisateur actuel peut approuver cette demande"
    )
    can_reject = fields.Boolean(
        compute='_compute_can_reject',
        string='Peut refuser',
        help="Indique si l'utilisateur actuel peut refuser cette demande"
    )
    can_cancel = fields.Boolean(
        compute='_compute_can_cancel',
        string='Peut annuler',
        help="Indique si l'utilisateur actuel peut annuler cette demande"
    )
    
    @api.depends('new_start', 'new_end')
    def _compute_allocated_hours(self):
        """Calcule le nombre d'heures allouées pour la modification."""
        for modification in self:
            if modification.new_start and modification.new_end:
                delta = modification.new_end - modification.new_start
                modification.allocated_hours = delta.total_seconds() / 3600
            else:
                modification.allocated_hours = 0
    
    @api.depends('state')
    def _compute_can_approve(self):
        """Détermine si l'utilisateur actuel peut approuver cette demande."""
        is_manager = self.env.user.has_group('planning.group_planning_manager')
        for modification in self:
            modification.can_approve = modification.state == 'pending' and is_manager
    
    @api.depends('state')
    def _compute_can_reject(self):
        """Détermine si l'utilisateur actuel peut refuser cette demande."""
        is_manager = self.env.user.has_group('planning.group_planning_manager')
        for modification in self:
            modification.can_reject = modification.state == 'pending' and is_manager
    
    @api.depends('state', 'user_id')
    def _compute_can_cancel(self):
        """Détermine si l'utilisateur actuel peut annuler cette demande."""
        is_manager = self.env.user.has_group('planning.group_planning_manager')
        for modification in self:
            modification.can_cancel = (
                modification.state == 'pending' and 
                (modification.user_id.id == self.env.user.id or is_manager)
            )
    
    def action_approve(self):
        """Approuve la demande de modification."""
        self.ensure_one()
        if not self.can_approve:
            return False
        
        # Mettre à jour le créneau de planning
        self.slot_id.write({
            'start_datetime': self.new_start,
            'end_datetime': self.new_end,
            'allocated_hours': self.allocated_hours,
            'role_id': self.new_role_id.id if self.new_role_id else self.slot_id.role_id.id,
            'portal_modification_approved': 'approved',
            'portal_confirmed': False,  # Nécessite une nouvelle confirmation
        })
        
        # Mettre à jour la demande
        self.write({
            'state': 'approved',
            'approver_id': self.env.user.id,
            'approval_date': fields.Datetime.now()
        })
        
        # Envoyer une notification à l'employé
        self.message_post(
            body=_('Demande de modification approuvée par %s') % self.env.user.name,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
            partner_ids=[self.user_id.partner_id.id]
        )
        
        return True
    
    def action_reject(self):
        """Refuse la demande de modification."""
        self.ensure_one()
        if not self.can_reject:
            return False
        
        # Mettre à jour le créneau de planning
        self.slot_id.write({
            'portal_modification_approved': 'rejected'
        })
        
        # Mettre à jour la demande
        self.write({
            'state': 'rejected',
            'approver_id': self.env.user.id,
            'approval_date': fields.Datetime.now()
        })
        
        # Envoyer une notification à l'employé
        self.message_post(
            body=_('Demande de modification refusée par %s') % self.env.user.name,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
            partner_ids=[self.user_id.partner_id.id]
        )
        
        return True
    
    def action_cancel(self):
        """Annule la demande de modification."""
        self.ensure_one()
        if not self.can_cancel:
            return False
        
        # Mettre à jour le créneau de planning si c'est l'employé qui annule
        if self.user_id.id == self.env.user.id:
            self.slot_id.write({
                'portal_modification_approved': False,
                'portal_modified': False
            })
        
        # Mettre à jour la demande
        self.write({
            'state': 'cancelled',
            'approver_id': self.env.user.id,
            'approval_date': fields.Datetime.now()
        })
        
        # Envoyer une notification
        self.message_post(
            body=_('Demande de modification annulée par %s') % self.env.user.name,
            message_type='notification',
            subtype_xmlid='mail.mt_comment'
        )
        
        return True
