# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class PlanningExchange(models.Model):
    """Modèle pour les demandes d'échange de créneaux de planning via le portail."""
    _name = 'portal.planning.exchange'
    _description = 'Échange de Planning via Portail'
    _rec_name = 'name'
    _order = 'date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Référence',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Nouvel échange')
    )
    date = fields.Datetime(
        string='Date de demande',
        required=True,
        default=fields.Datetime.now,
        tracking=True
    )
    
    # Créneau source (celui que l'utilisateur souhaite échanger)
    source_slot_id = fields.Many2one(
        'planning.slot',
        string='Créneau à échanger',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    source_employee_id = fields.Many2one(
        'hr.employee',
        string='Employé source',
        related='source_slot_id.employee_id',
        store=True,
        readonly=True
    )
    source_user_id = fields.Many2one(
        'res.users',
        string='Demandeur',
        required=True,
        default=lambda self: self.env.user.id,
        tracking=True
    )
    source_start = fields.Datetime(
        string='Début source',
        related='source_slot_id.start_datetime',
        store=True,
        readonly=True
    )
    source_end = fields.Datetime(
        string='Fin source',
        related='source_slot_id.end_datetime',
        store=True,
        readonly=True
    )
    source_role_id = fields.Many2one(
        'planning.role',
        string='Rôle source',
        related='source_slot_id.role_id',
        store=True,
        readonly=True
    )
    
    # Créneau cible (celui avec lequel l'utilisateur souhaite échanger)
    target_slot_id = fields.Many2one(
        'planning.slot',
        string='Créneau souhaité',
        ondelete='cascade',
        tracking=True
    )
    target_employee_id = fields.Many2one(
        'hr.employee',
        string='Employé cible',
        related='target_slot_id.employee_id',
        store=True,
        readonly=True
    )
    target_user_id = fields.Many2one(
        'res.users',
        string='Destinataire',
        related='target_employee_id.user_id',
        store=True,
        readonly=True
    )
    target_start = fields.Datetime(
        string='Début cible',
        related='target_slot_id.start_datetime',
        store=True,
        readonly=True
    )
    target_end = fields.Datetime(
        string='Fin cible',
        related='target_slot_id.end_datetime',
        store=True,
        readonly=True
    )
    target_role_id = fields.Many2one(
        'planning.role',
        string='Rôle cible',
        related='target_slot_id.role_id',
        store=True,
        readonly=True
    )
    
    # Dates libres (si l'utilisateur souhaite échanger avec n'importe qui)
    is_open_request = fields.Boolean(
        string='Demande ouverte',
        default=False,
        help="Si activé, la demande est ouverte à tous les employés disponibles"
    )
    preferred_start = fields.Datetime(
        string='Début préféré',
        help="Date de début préférée pour l'échange (si demande ouverte)"
    )
    preferred_end = fields.Datetime(
        string='Fin préférée',
        help="Date de fin préférée pour l'échange (si demande ouverte)"
    )
    
    # Suivi de la demande
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('pending', 'En attente'),
        ('accepted', 'Accepté par l\'employé'),
        ('approved', 'Approuvé'),
        ('rejected', 'Refusé'),
        ('cancelled', 'Annulé')
    ], string='État', default='draft', tracking=True, copy=False)
    
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
    can_submit = fields.Boolean(
        compute='_compute_can_submit',
        string='Peut soumettre',
        help="Indique si l'utilisateur actuel peut soumettre cette demande"
    )
    can_accept = fields.Boolean(
        compute='_compute_can_accept',
        string='Peut accepter',
        help="Indique si l'utilisateur actuel peut accepter cette demande"
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
    
    @api.model_create_multi
    def create(self, vals_list):
        """Génère une séquence unique pour chaque nouvelle demande d'échange."""
        for vals in vals_list:
            if vals.get('name', _('Nouvel échange')) == _('Nouvel échange'):
                vals['name'] = self.env['ir.sequence'].next_by_code('portal.planning.exchange') or _('Nouvel échange')
        return super(PlanningExchange, self).create(vals_list)
    
    @api.depends('state', 'source_user_id')
    def _compute_can_submit(self):
        """Détermine si l'utilisateur actuel peut soumettre cette demande."""
        for exchange in self:
            exchange.can_submit = (
                exchange.state == 'draft' and 
                exchange.source_user_id.id == self.env.user.id
            )
    
    @api.depends('state', 'target_user_id')
    def _compute_can_accept(self):
        """Détermine si l'utilisateur actuel peut accepter cette demande."""
        for exchange in self:
            exchange.can_accept = (
                exchange.state == 'pending' and 
                exchange.target_user_id.id == self.env.user.id
            )
    
    @api.depends('state')
    def _compute_can_approve(self):
        """Détermine si l'utilisateur actuel peut approuver cette demande."""
        is_manager = self.env.user.has_group('planning.group_planning_manager')
        for exchange in self:
            exchange.can_approve = exchange.state == 'accepted' and is_manager
    
    @api.depends('state')
    def _compute_can_reject(self):
        """Détermine si l'utilisateur actuel peut refuser cette demande."""
        is_manager = self.env.user.has_group('planning.group_planning_manager')
        for exchange in self:
            exchange.can_reject = exchange.state in ['pending', 'accepted'] and (
                is_manager or 
                exchange.target_user_id.id == self.env.user.id
            )
    
    @api.depends('state', 'source_user_id')
    def _compute_can_cancel(self):
        """Détermine si l'utilisateur actuel peut annuler cette demande."""
        is_manager = self.env.user.has_group('planning.group_planning_manager')
        for exchange in self:
            exchange.can_cancel = (
                exchange.state in ['draft', 'pending', 'accepted'] and 
                (exchange.source_user_id.id == self.env.user.id or is_manager)
            )
    
    def action_submit(self):
        """Soumet la demande d'échange."""
        self.ensure_one()
        if not self.can_submit:
            return False
        
        # Vérifier que le créneau source appartient bien à l'utilisateur
        if self.source_slot_id.employee_id.user_id.id != self.env.user.id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('Vous ne pouvez échanger que vos propres créneaux de planning.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        
        # Vérifier que le créneau cible existe si ce n'est pas une demande ouverte
        if not self.is_open_request and not self.target_slot_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('Veuillez sélectionner un créneau cible ou activer la demande ouverte.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        
        # Vérifier que les dates préférées sont renseignées si c'est une demande ouverte
        if self.is_open_request and (not self.preferred_start or not self.preferred_end):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('Veuillez renseigner les dates préférées pour une demande ouverte.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        
        # Mettre à jour l'état de la demande
        self.write({
            'state': 'pending',
            'date': fields.Datetime.now()
        })
        
        # Envoyer une notification au destinataire si ce n'est pas une demande ouverte
        if not self.is_open_request and self.target_user_id:
            self.message_post(
                body=_('%s souhaite échanger son créneau du %s avec votre créneau du %s') % (
                    self.source_employee_id.name,
                    self.source_start.strftime('%d/%m/%Y %H:%M'),
                    self.target_start.strftime('%d/%m/%Y %H:%M')
                ),
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
                partner_ids=[self.target_user_id.partner_id.id]
            )
        
        return True
    
    def action_accept(self):
        """Accepte la demande d'échange (par l'employé cible)."""
        self.ensure_one()
        if not self.can_accept:
            return False
        
        # Mettre à jour l'état de la demande
        self.write({
            'state': 'accepted',
        })
        
        # Envoyer une notification au demandeur
        self.message_post(
            body=_('%s a accepté votre demande d\'échange. En attente d\'approbation par un responsable.') % self.target_employee_id.name,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
            partner_ids=[self.source_user_id.partner_id.id]
        )
        
        return True
    
    def action_approve(self):
        """Approuve la demande d'échange (par un responsable)."""
        self.ensure_one()
        if not self.can_approve:
            return False
        
        # Échanger les employés des créneaux
        source_employee = self.source_slot_id.employee_id
        target_employee = self.target_slot_id.employee_id
        
        self.source_slot_id.write({
            'employee_id': target_employee.id,
            'portal_confirmed': False,  # Nécessite une nouvelle confirmation
        })
        
        self.target_slot_id.write({
            'employee_id': source_employee.id,
            'portal_confirmed': False,  # Nécessite une nouvelle confirmation
        })
        
        # Mettre à jour l'état de la demande
        self.write({
            'state': 'approved',
            'approver_id': self.env.user.id,
            'approval_date': fields.Datetime.now()
        })
        
        # Envoyer des notifications aux employés
        self.message_post(
            body=_('Votre demande d\'échange a été approuvée par %s. Les créneaux ont été échangés.') % self.env.user.name,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
            partner_ids=[self.source_user_id.partner_id.id, self.target_user_id.partner_id.id]
        )
        
        return True
    
    def action_reject(self):
        """Refuse la demande d'échange."""
        self.ensure_one()
        if not self.can_reject:
            return False
        
        # Mettre à jour l'état de la demande
        self.write({
            'state': 'rejected',
            'approver_id': self.env.user.id if self.env.user.has_group('planning.group_planning_manager') else False,
            'approval_date': fields.Datetime.now() if self.env.user.has_group('planning.group_planning_manager') else False
        })
        
        # Envoyer une notification au demandeur
        if self.env.user.id == self.target_user_id.id:
            message = _('%s a refusé votre demande d\'échange.') % self.target_employee_id.name
        else:
            message = _('Votre demande d\'échange a été refusée par %s.') % self.env.user.name
        
        self.message_post(
            body=message,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
            partner_ids=[self.source_user_id.partner_id.id]
        )
        
        return True
    
    def action_cancel(self):
        """Annule la demande d'échange."""
        self.ensure_one()
        if not self.can_cancel:
            return False
        
        # Mettre à jour l'état de la demande
        self.write({
            'state': 'cancelled',
        })
        
        # Envoyer une notification
        if self.env.user.id == self.source_user_id.id:
            message = _('Vous avez annulé votre demande d\'échange.')
            partners = []
            if self.target_user_id:
                partners.append(self.target_user_id.partner_id.id)
        else:
            message = _('Votre demande d\'échange a été annulée par %s.') % self.env.user.name
            partners = [self.source_user_id.partner_id.id]
        
        if partners:
            self.message_post(
                body=message,
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
                partner_ids=partners
            )
        
        return True
