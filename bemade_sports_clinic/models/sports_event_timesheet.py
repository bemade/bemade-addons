from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SportsEventTimesheet(models.Model):
    _name = 'sports.event.timesheet'
    _description = 'Sports Event Timesheet'
    _order = 'coverage_start asc'

    event_id = fields.Many2one(
        'sports.event',
        string='Event',
        required=True,
        ondelete='cascade',
        index=True,
        help='Event this timesheet belongs to'
    )

    user_id = fields.Many2one(
        'res.users',
        string='Therapist',
        required=True,
        index=True,
        help='Therapist entering this timesheet'
    )

    # State
    state = fields.Selection(
        [
            ('submitted', 'Submitted'),
            ('invoiced', 'Invoiced'),
        ],
        string='Status',
        default='submitted',
        index=True,
        help='Submitted: editable; Invoiced: read-only'
    )

    # Times
    travel_start = fields.Datetime(string='Travel Start')
    coverage_start = fields.Datetime(string='Coverage Start')
    coverage_end = fields.Datetime(string='Coverage End')
    travel_end = fields.Datetime(string='Travel End')

    # Computed durations
    coverage_duration = fields.Float(
        string='Coverage Duration (Hours)',
        compute='_compute_durations',
        store=True,
        help='Hours of coverage (coverage_end - coverage_start)'
    )

    travel_duration = fields.Float(
        string='Travel Duration (Hours)',
        compute='_compute_durations',
        store=True,
        help='Total travel time before and after coverage'
    )

    _sql_constraints = [
        ('event_user_unique', 'unique(event_id, user_id)', 'Each therapist may only have one timesheet per event.'),
    ]

    # ------------------------------------------------------
    # DEFAULTS + ONCHANGES (so values show before write)
    # ------------------------------------------------------

    @api.model
    def default_get(self, fields_list):
        """Prefill times based on event when opening a fresh record (form or inline)."""
        res = super().default_get(fields_list)
        event_id = self.env.context.get('default_event_id')
        event = self.env['sports.event'].browse(event_id) if event_id else self.env['sports.event']

        cov_start = event and (event.therapist_start or event.date_start) or False
        cov_end = event and (event.therapist_end or event.date_end) or False

        if 'event_id' in fields_list and not res.get('event_id') and event_id:
            res['event_id'] = event_id
        if 'user_id' in fields_list and not res.get('user_id'):
            res['user_id'] = self.env.user.id
        if 'state' in fields_list and not res.get('state'):
            res['state'] = 'submitted'
        if 'coverage_start' in fields_list and not res.get('coverage_start'):
            res['coverage_start'] = cov_start
        if 'coverage_end' in fields_list and not res.get('coverage_end'):
            res['coverage_end'] = cov_end
        if 'travel_start' in fields_list and not res.get('travel_start'):
            res['travel_start'] = res.get('coverage_start') or cov_start
        if 'travel_end' in fields_list and not res.get('travel_end'):
            res['travel_end'] = res.get('coverage_end') or cov_end
        return res

    @api.onchange('event_id')
    def _onchange_event_id(self):
        """When changing event, prefill times if empty so the user sees defaults immediately."""
        event = self.event_id
        if not event:
            return
        cov_start = event.therapist_start or event.date_start
        cov_end = event.therapist_end or event.date_end
        if not self.coverage_start:
            self.coverage_start = cov_start
        if not self.coverage_end:
            self.coverage_end = cov_end
        if not self.travel_start:
            self.travel_start = self.coverage_start or cov_start
        if not self.travel_end:
            self.travel_end = self.coverage_end or cov_end

    @api.onchange('coverage_start')
    def _onchange_coverage_start(self):
        """If travel_start is not set, align it to coverage_start on change."""
        if self.coverage_start and not self.travel_start:
            self.travel_start = self.coverage_start

    @api.onchange('coverage_end')
    def _onchange_coverage_end(self):
        """If travel_end is not set, align it to coverage_end on change."""
        if self.coverage_end and not self.travel_end:
            self.travel_end = self.coverage_end

    @api.model_create_multi
    def create(self, vals_list):
        # Default times from the event if not provided
        for vals in vals_list:
            event = None
            if vals.get('event_id'):
                event = self.env['sports.event'].browse(vals['event_id'])
            # Default coverage to therapist times
            if event:
                if not vals.get('coverage_start'):
                    vals['coverage_start'] = event.therapist_start or event.date_start
                if not vals.get('coverage_end'):
                    vals['coverage_end'] = event.therapist_end or event.date_end
                # Default travel to coverage if not provided
                if not vals.get('travel_start'):
                    vals['travel_start'] = vals.get('coverage_start')
                if not vals.get('travel_end'):
                    vals['travel_end'] = vals.get('coverage_end')
            # Ensure default state
            vals.setdefault('state', 'submitted')
        return super().create(vals_list)

    def write(self, vals):
        # Prevent editing invoiced records (read-only)
        if any(rec.state == 'invoiced' for rec in self):
            # Allow no-op state write (e.g., writing the same state) and block changes to other fields
            blocked_fields = set(vals.keys()) - {'state'}
            if blocked_fields or (vals.get('state') and any(rec.state == 'invoiced' and vals.get('state') != 'invoiced' for rec in self)):
                raise ValidationError('Timesheets are read-only once invoiced.')
        return super().write(vals)

    def unlink(self):
        if any(rec.state == 'invoiced' for rec in self):
            raise ValidationError('Invoiced timesheets cannot be deleted.')
        return super().unlink()

    @api.depends('coverage_start', 'coverage_end', 'travel_start', 'travel_end')
    def _compute_durations(self):
        for ts in self:
            # Coverage duration
            if ts.coverage_start and ts.coverage_end and ts.coverage_end > ts.coverage_start:
                cov = (ts.coverage_end - ts.coverage_start).total_seconds() / 3600.0
            else:
                cov = 0.0
            # Travel before and after coverage
            before = 0.0
            after = 0.0
            if ts.travel_start and ts.coverage_start and ts.coverage_start > ts.travel_start:
                before = (ts.coverage_start - ts.travel_start).total_seconds() / 3600.0
            if ts.travel_end and ts.coverage_end and ts.travel_end > ts.coverage_end:
                after = (ts.travel_end - ts.coverage_end).total_seconds() / 3600.0
            ts.coverage_duration = cov
            ts.travel_duration = max(0.0, before) + max(0.0, after)

    @api.constrains('coverage_start', 'coverage_end', 'travel_start', 'travel_end')
    def _check_times(self):
        for ts in self:
            # Basic ordering constraints
            if ts.coverage_start and ts.coverage_end and ts.coverage_end <= ts.coverage_start:
                raise ValidationError('Coverage end must be after coverage start.')
            if ts.travel_start and ts.coverage_start and ts.travel_start > ts.coverage_start:
                raise ValidationError('Travel start must be on or before coverage start.')
            if ts.travel_end and ts.coverage_end and ts.travel_end < ts.coverage_end:
                raise ValidationError('Travel end must be on or after coverage end.')
