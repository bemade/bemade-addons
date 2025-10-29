from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SportsEvent(models.Model):
    _name = 'sports.event'
    _description = 'Sports Event'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start asc, name'
    _rec_name = 'name'

    # Portal access group definition - only authorized portal users
    _portal_groups = 'base.group_user,bemade_sports_clinic.group_portal_treatment_professional,bemade_sports_clinic.group_portal_team_coach'

    # ========================================
    # CORE EVENT FIELDS (Portal Accessible)
    # ========================================
    
    name = fields.Char(
        string='Event Name',
        required=True,
        tracking=True,
        groups=_portal_groups,
        help='Name of the sports event'
    )
    
    description = fields.Html(
        string='Description',
        groups=_portal_groups,
        help='Detailed description of the event'
    )
    
    # Event timing
    date_start = fields.Datetime(
        string='Event Start Time',
        required=True,
        tracking=True,
        index=True,
        groups=_portal_groups,
        default=fields.Datetime.now,
        help='When the event starts'
    )
    
    date_end = fields.Datetime(
        string='Event End Time',
        required=True,
        tracking=True,
        index=True,
        groups=_portal_groups,
        help='When the event ends'
    )
    
    # Therapist coverage timing (independent fields that sync with task)
    therapist_start = fields.Datetime(
        string='Therapist Start Time',
        tracking=True,
        index=True,
        groups=_portal_groups,
        help='When therapist coverage begins (may be before event start for preparation)'
    )
    
    therapist_end = fields.Datetime(
        string='Therapist End Time',
        tracking=True,
        index=True,
        groups=_portal_groups,
        help='When therapist coverage ends (may be after event end for cleanup)'
    )
    
    # Event details
    venue_id = fields.Many2one(
        'res.partner',
        string='Venue',
        domain=[('is_venue', '=', True)],
        groups=_portal_groups,
        help='Venue/location where the event takes place'
    )
    
    event_type = fields.Selection([
        ('game', 'Game'),
        ('practice', 'Practice'),
        ('training', 'Training'),
        ('meeting', 'Team Meeting'),
        ('clinic', 'Clinic'),
        ('other', 'Other')
    ], string='Event Type', default='game', groups=_portal_groups, tracking=True)
    
    # Status and priority
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('to_invoice', 'To Invoice'),
        ('invoiced', 'Invoiced'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='confirmed', tracking=True, groups=_portal_groups)
    
    # ========================================
    # RELATIONSHIPS (Portal Accessible)
    # ========================================
    
    team_id = fields.Many2one(
        'sports.team',
        string='Team',
        required=True,
        tracking=True,
        groups=_portal_groups,
        help='The sports team this event is for'
    )
    
    # Staff assignments
    assigned_staff_ids = fields.Many2many(
        'res.users',
        'sports_event_staff_rel',
        'event_id',
        'user_id',
        string='Assigned Staff',
        groups=_portal_groups,
        help='Treatment professionals assigned to this event'
    )

    # Timesheets: one per assigned therapist
    timesheet_ids = fields.One2many(
        'sports.event.timesheet', 'event_id',
        string='Timesheets',
        help='Timesheets logged by assigned therapists for this event'
    )

    timesheet_count = fields.Integer(
        string='Timesheet Count',
        compute='_compute_timesheet_count',
        store=False,
        help='Number of timesheets recorded for this event'
    )
    
    # ========================================
    # TASK INTEGRATION (Internal Management)
    # ========================================
    
    task_id = fields.Many2one(
        'project.task',
        string='Management Task',
        ondelete='set null',
        groups='base.group_user',
        help='Internal project task for managing this event'
    )
    
    project_id = fields.Many2one(
        'project.project',
        string='Project',
        groups='base.group_user',
        help='Project this event belongs to'
    )
    
    # ========================================
    # COMPUTED FIELDS
    # ========================================
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Organization',
        compute='_compute_partner_id',
        store=True,
        groups=_portal_groups,
        help='Parent organization (computed from team)'
    )
    
    duration = fields.Float(
        string='Event Duration (Hours)',
        compute='_compute_duration',
        store=True,
        groups=_portal_groups,
        help='Event duration in hours'
    )
    
    therapist_duration = fields.Float(
        string='Therapist Coverage Duration (Hours)',
        compute='_compute_therapist_duration',
        store=True,
        groups=_portal_groups,
        help='Therapist coverage duration in hours'
    )

    # Billing readiness flags
    has_uninvoiced_timesheets = fields.Boolean(
        string='Has Uninvoiced Timesheets',
        compute='_compute_has_uninvoiced_timesheets',
        store=False,
        help='True when any timesheet still needs customer invoicing (coverage or travel)'
    )
    
    is_today = fields.Boolean(
        string='Is Today',
        compute='_compute_is_today',
        help='Whether the event is happening today'
    )
    
    is_upcoming = fields.Boolean(
        string='Is Upcoming',
        compute='_compute_is_upcoming',
        help='Whether the event is in the future'
    )

    # Helper field used in views to filter staff pickers to treatment professionals only
    treatment_professional_user_ids = fields.Many2many(
        'res.users',
        string='Treatment Professional Users',
        compute='_compute_treatment_professional_user_ids',
        store=False,
        help='All users who are treatment professionals (internal and portal). Used to filter staff selection.'
    )
    
    # ========================================
    # COMPUTED METHODS
    # ========================================
    
    @api.depends('team_id', 'team_id.parent_id')
    def _compute_partner_id(self):
        """Compute partner/organization from team"""
        for event in self:
            event.partner_id = event.team_id.parent_id if event.team_id else False
    
    def action_recompute_partner_ids(self):
        """Recompute partner_id for all events (for fixing organization filter)"""
        all_events = self.search([])
        all_events._compute_partner_id()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Recomputed partner_id for {len(all_events)} events',
                'type': 'success',
            }
        }
    
    @api.depends('date_start', 'date_end')
    def _compute_duration(self):
        """Calculate event duration in hours"""
        for event in self:
            if event.date_start and event.date_end:
                delta = event.date_end - event.date_start
                event.duration = delta.total_seconds() / 3600.0
            else:
                event.duration = 0.0
    
    @api.depends('therapist_start', 'therapist_end')
    def _compute_therapist_duration(self):
        """Calculate therapist coverage duration in hours"""
        for event in self:
            if event.therapist_start and event.therapist_end:
                delta = event.therapist_end - event.therapist_start
                event.therapist_duration = delta.total_seconds() / 3600.0
            else:
                event.therapist_duration = 0.0

    def _compute_has_uninvoiced_timesheets(self):
        for event in self:
            ts = event.timesheet_ids
            event.has_uninvoiced_timesheets = any(t.customer_ready_to_invoice for t in ts)
    
    @api.depends('date_start')
    def _compute_is_today(self):
        """Check if event is today"""
        from datetime import date
        today = date.today()
        for event in self:
            if event.date_start:
                event.is_today = event.date_start.date() == today
            else:
                event.is_today = False
    
    @api.depends('date_start')
    def _compute_is_upcoming(self):
        """Check if event is in the future"""
        from datetime import datetime
        now = datetime.now()
        for event in self:
            if event.date_start:
                event.is_upcoming = event.date_start > now
            else:
                event.is_upcoming = False

    def _compute_treatment_professional_user_ids(self):
        """Compute the list of users who are treatment professionals.

        Includes both internal treatment professionals and portal treatment professionals.
        """
        # Resolve groups safely via env.ref
        tp_internal = self.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional', raise_if_not_found=False)
        tp_portal = self.env.ref('bemade_sports_clinic.group_portal_treatment_professional', raise_if_not_found=False)
        group_ids = [g.id for g in (tp_internal, tp_portal) if g]

        users = self.env['res.users']
        if group_ids:
            users = users.search([('active', '=', True), ('groups_id', 'in', group_ids)])
        else:
            users = users.browse()

        for event in self:
            event.treatment_professional_user_ids = users

    def _compute_timesheet_count(self):
        for event in self:
            event.timesheet_count = len(event.timesheet_ids)
    
    # ========================================
    # ONCHANGE METHODS
    # ========================================
    
    @api.onchange('date_start')
    def _onchange_date_start(self):
        """When event start changes:
        - therapist_start defaults to same as date_start if not already set
        - date_end defaults to +2 hours only if not already set or invalid
        - therapist_end defaults to date_end if not already set
        """
        if self.date_start:
            from datetime import timedelta
            # Respect existing values (e.g., provided from calendar selection)
            if not self.therapist_start:
                self.therapist_start = self.date_start
            # If no date_end or it's earlier/equal to start, set sensible default
            if not self.date_end or self.date_end <= self.date_start:
                self.date_end = self.date_start + timedelta(hours=2)
            # Only set therapist_end if not already provided
            if not self.therapist_end:
                self.therapist_end = self.date_end

    @api.onchange('date_end')
    def _onchange_date_end(self):
        """When event end changes:
        - therapist_end = max(therapist_end, date_end)
        """
        if self.date_end:
            # If therapist_end not set or earlier than date_end, align to date_end
            if not self.therapist_end or self.therapist_end < self.date_end:
                self.therapist_end = self.date_end

    @api.onchange('team_id')
    def _onchange_team_id_prefill_head_therapist(self):
        """When a team is selected, prefill assigned staff with the head therapist's user
        if none is assigned yet. Non-destructive: will not override existing selections.
        """
        if self.team_id and not self.assigned_staff_ids:
            partner = self.team_id.head_therapist_id
            if partner and partner.user_ids:
                user = partner.user_ids.filtered(lambda u: u.active)[:1]
                if user:
                    # Add without replacing future manual changes
                    self.assigned_staff_ids = [(6, 0, [user.id])]

    # ========================================
    # DEFAULTS / INITIALIZATION
    # ========================================
    @api.model
    def default_get(self, fields_list):
        """Initialize date_start/date_end from calendar selection when available.

        The calendar view for this model uses `therapist_start`/`therapist_end` as
        the date_start/date_stop fields. When a user selects a range and creates
        a new record from the calendar, Odoo puts those in context as
        `default_therapist_start` and `default_therapist_end`.

        We map them to `date_start`/`date_end` if those are not already provided
        in the defaults, so the form respects the selected range instead of
        overriding with field defaults or onchange logic.
        """
        values = super().default_get(fields_list)
        ctx = self.env.context or {}

        # Extract calendar-provided defaults
        cal_start = ctx.get('default_therapist_start')
        cal_end = ctx.get('default_therapist_end')

        # If the calendar provided a selection, prefer it over field defaults
        from datetime import timedelta
        if 'date_start' in self._fields and cal_start:
            values['date_start'] = cal_start
        if 'date_end' in self._fields:
            if cal_end:
                values['date_end'] = cal_end
            elif values.get('date_start') and not values.get('date_end'):
                # Provide a sensible default (+2 hours) if only start is given
                values['date_end'] = values['date_start'] + timedelta(hours=2)

        # Also ensure therapist_* align with provided calendar values if absent
        if 'therapist_start' in self._fields and not values.get('therapist_start') and cal_start:
            values['therapist_start'] = cal_start
        if 'therapist_end' in self._fields and not values.get('therapist_end'):
            if cal_end:
                values['therapist_end'] = cal_end
            elif values.get('date_end'):
                values['therapist_end'] = values['date_end']

        # Do not prefill assigned staff by default
        try:
            Team = self.env['sports.team']
            team_id_ctx = (self.env.context or {}).get('default_team_id')
            team_id_val = values.get('team_id') or team_id_ctx
            if team_id_val and not values.get('assigned_staff_ids'):
                pass
        except Exception:
            pass

        return values

    # ========================================
    # VALIDATION
    # ========================================
    
    @api.constrains('date_start', 'date_end')
    def _check_event_dates(self):
        """Validate that end date is after start date"""
        for event in self:
            if event.date_start and event.date_end:
                if event.date_end <= event.date_start:
                    raise ValidationError("Event end time must be after start time.")
    
    @api.constrains('therapist_start', 'therapist_end')
    def _check_therapist_dates(self):
        """Validate that therapist end time is after start time"""
        for event in self:
            if event.therapist_start and event.therapist_end:
                if event.therapist_end <= event.therapist_start:
                    raise ValidationError("Therapist end time must be after start time.")
    
    # ========================================
    # TASK INTEGRATION METHODS
    # ========================================
    
    def create_management_task(self):
        """Create a project task for internal management of this event"""
        self.ensure_one()
        if self.task_id:
            return self.task_id
        
        # Find or create a project for the team
        project = self._get_or_create_team_project()
        
        task_vals = {
            'name': f"Event: {self.name}",
            'description': self.description or '',
            'project_id': project.id,
            'date_deadline': self.date_end,
            'user_ids': [(6, 0, self.assigned_staff_ids.ids)],
            'partner_id': self.partner_id.id if self.partner_id else False,
        }
        
        task = self.env['project.task'].create(task_vals)
        self.task_id = task.id
        self.project_id = project.id
        
        return task
    
    def _get_or_create_team_project(self):
        """Get or create a project for the organization (one project per partner for billing)"""
        if self.project_id:
            return self.project_id
        
        # Get the organization (partner) from the team
        organization = self.team_id.parent_id if self.team_id else False
        if not organization:
            raise ValidationError("Team must have a parent organization to create events.")
        
        # Look for existing organization project (one project per partner)
        project = self.env['project.project'].search([
            ('partner_id', '=', organization.id),
        ], limit=1)
        
        if not project:
            # Create new project for the organization
            project = self.env['project.project'].create({
                'name': f"{organization.name} - Sports Events",
                'partner_id': organization.id,
                'privacy_visibility': 'portal',
                'description': f"Event management for {organization.name} sports teams"
            })
        
        return project
    
    # ========================================
    # PORTAL ACCESS METHODS
    # ========================================
    
    def check_portal_access(self, user=None):
        """Check if user has portal access to this event"""
        if not user:
            user = self.env.user
        
        # Internal users have full access
        if user.has_group('base.group_user'):
            return True
        
        # Portal treatment professionals need team access
        if user.has_group('bemade_sports_clinic.group_portal_treatment_professional'):
            partner = user.partner_id
            team_staff_rels = partner.team_staff_rel_ids
            authorized_teams = team_staff_rels.mapped('team_id')
            return self.team_id in authorized_teams
        
        return False
    
    # ========================================
    # CRUD OVERRIDES
    # ========================================
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle task integration (batch-optimized for Odoo 18)"""
        events = super().create(vals_list)
        
        # Auto-create management tasks for events that need them
        # IMPORTANT: Only internal users (base.group_user) may auto-create tasks here.
        # Portal users will have tasks created via a controller-side sudo() after access checks.
        is_internal = self.env.user.has_group('base.group_user')
        if is_internal:
            for event, vals in zip(events, vals_list):
                if vals.get('auto_create_task', True):
                    event.create_management_task()
        
        return events
    
    def write(self, vals):
        """Override write to sync with task"""
        result = super().write(vals)
        
        # Sync changes to linked task (only for users with task access)
        user = self.env.user
        has_task_access = user.has_group('base.group_user')
        
        if has_task_access:
            for event in self:
                if event.task_id:
                    event._sync_to_task()
        
        return result
    
    def _sync_to_task(self):
        """Sync event changes to linked task"""
        if not self.task_id:
            return
        
        task_vals = {
            'name': f"Event: {self.name}",
            'description': self.description or '',
            'date_deadline': self.date_end,
            'user_ids': [(6, 0, self.assigned_staff_ids.ids)],
        }
        
        # Sync therapist coverage times to task start/end times
        if self.therapist_start:
            task_vals['date_start'] = self.therapist_start
        if self.therapist_end:
            task_vals['date_end'] = self.therapist_end
        
        self.task_id.write(task_vals)

    # ========================================
    # INTERNAL WORKFLOW ACTIONS
    # ========================================
    def action_mark_in_progress(self):
        """Mark event as In Progress (internal users only)"""
        internal_user = self.env.user.has_group('base.group_user')
        if not internal_user:
            # Safety guard: internal-only
            raise ValidationError("Only internal users can change event workflow state.")
        for event in self:
            if event.state in ('draft', 'confirmed'):
                event.write({'state': 'in_progress'})
                try:
                    event.message_post(body="Event marked In Progress")
                except Exception:
                    pass
        return True

    def action_mark_completed(self):
        """Mark event as Completed (internal users only)"""
        internal_user = self.env.user.has_group('base.group_user')
        if not internal_user:
            raise ValidationError("Only internal users can change event workflow state.")
        for event in self:
            if event.state in ('in_progress', 'confirmed', 'draft'):
                # Non-blocking warning if not all assigned therapists have timesheets
                missing_users = event._get_missing_timesheet_user_ids()
                if missing_users:
                    # Notify but do not block
                    try:
                        names = ', '.join(missing_users.mapped('name'))
                        event.message_post(body=f"Warning: Completing event without timesheets for: {names}")
                    except Exception:
                        pass
                # If any timesheets remain to invoice, move to 'to_invoice' directly
                next_state = 'to_invoice' if any(event.timesheet_ids.mapped('customer_ready_to_invoice')) else 'completed'
                event.write({'state': next_state})
                try:
                    msg = "Event marked To Invoice" if next_state == 'to_invoice' else "Event marked Completed"
                    event.message_post(body=msg)
                except Exception:
                    pass
        return True

    # ========================================
    # HELPERS
    # ========================================
    def _get_missing_timesheet_user_ids(self):
        """Return res.users records for assigned staff who do not have a timesheet yet"""
        self.ensure_one()
        assigned = self.assigned_staff_ids
        if not assigned:
            return self.env['res.users']
        have_ts_users = self.timesheet_ids.mapped('user_id')
        missing = assigned - have_ts_users
        return missing

    def action_mark_invoiced(self):
        """Mark event as Invoiced (internal users only). Typically done after billing."""
        internal_user = self.env.user.has_group('base.group_user')
        if not internal_user:
            raise ValidationError("Only internal users can change event workflow state.")
        for event in self:
            # Allow invoiced from completed or cancelled (if billed anyway), and idempotent
            if event.state in ('completed', 'to_invoice', 'cancelled', 'invoiced'):
                event.write({'state': 'invoiced'})
                try:
                    event.message_post(body="Event marked Invoiced")
                except Exception:
                    pass
        return True
