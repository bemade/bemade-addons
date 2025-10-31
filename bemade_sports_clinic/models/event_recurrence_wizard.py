from odoo import api, fields, models
from odoo.exceptions import UserError
from datetime import datetime, timedelta, date
import pytz


class SportsEventRecurrencePreview(models.TransientModel):
    _name = 'sports.event.recurrence.preview'
    _description = 'Sports Event Recurrence Preview Line'

    wizard_id = fields.Many2one('sports.event.recurrence.wizard', required=True, ondelete='cascade')
    date_start = fields.Datetime(string='Start')
    date_end = fields.Datetime(string='End')


class SportsEventRecurrenceWizard(models.TransientModel):
    _name = 'sports.event.recurrence.wizard'
    _description = 'Create Recurrent Copies of Event'

    base_event_id = fields.Many2one('sports.event', string='Base Event', required=True, readonly=True)

    timezone = fields.Char(string='Timezone', help='Timezone used to compute occurrences at a fixed local wall time.',
                           default=lambda self: self.env.user.tz or (self.env.context or {}).get('tz') or '')

    interval_weeks = fields.Integer(string='Repeat every (weeks)', default=1, required=True)

    by_mo = fields.Boolean(string='Mon', default=False)
    by_tu = fields.Boolean(string='Tue', default=False)
    by_we = fields.Boolean(string='Wed', default=False)
    by_th = fields.Boolean(string='Thu', default=False)
    by_fr = fields.Boolean(string='Fri', default=False)
    by_sa = fields.Boolean(string='Sat', default=False)
    by_su = fields.Boolean(string='Sun', default=False)

    end_mode = fields.Selection([
        ('until', 'End by date'),
        ('count', 'End after N occurrences'),
    ], default='until', required=True)

    until_date = fields.Date(string='Until')
    count = fields.Integer(string='Occurrences', default=6)

    recurrence_state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], string='State for new events', default='confirmed', required=True)

    preview_count = fields.Integer(string='Will create')
    preview_line_ids = fields.One2many('sports.event.recurrence.preview', 'wizard_id', string='Preview Dates')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        if active_model != 'sports.event' or not active_id:
            raise UserError('Open this wizard from an Event.')
        res['base_event_id'] = active_id
        # Default weekday of the base event
        base = self.env['sports.event'].browse(active_id)
        if base and base.date_start:
            wd = base.date_start.weekday()  # 0=Mon
            key_map = {0: 'by_mo', 1: 'by_tu', 2: 'by_we', 3: 'by_th', 4: 'by_fr', 5: 'by_sa', 6: 'by_su'}
            res[key_map.get(wd)] = True
        # Default until one month from base start
        if base and base.date_start:
            res['until_date'] = (base.date_start.date() + timedelta(weeks=4))
        return res

    def _selected_weekdays(self):
        self.ensure_one()
        flags = [self.by_mo, self.by_tu, self.by_we, self.by_th, self.by_fr, self.by_sa, self.by_su]
        return [i for i, v in enumerate(flags) if v]

    def _generate_occurrence_datetimes(self):
        self.ensure_one()
        base = self.base_event_id
        if not base or not base.date_start or not base.date_end:
            return []
        if self.interval_weeks < 1:
            raise UserError('Interval must be at least 1 week.')
        # Validate end conditions (Odoo 18: do not rely on view attrs)
        if self.end_mode == 'until':
            if not self.until_date:
                raise UserError('Please select an Until date for the recurrence.')
        elif self.end_mode == 'count':
            if not self.count or self.count <= 0:
                raise UserError('Please enter a positive number of occurrences.')
        # Require timezone for correct DST handling
        tz_name = (self.timezone or '').strip() or (self.env.context or {}).get('tz') or self.env.user.tz
        if not tz_name:
            raise UserError('Please set your user Timezone in Preferences or fill the Timezone field on this wizard to compute local times.')
        # Timezone-aware handling to keep the same local time across DST changes
        tz = pytz.timezone(tz_name)

        start_dt_utc = fields.Datetime.to_datetime(base.date_start)
        end_dt_utc = fields.Datetime.to_datetime(base.date_end)

        # Convert base to local time
        start_dt_local = start_dt_utc.astimezone(tz)
        end_dt_local = end_dt_utc.astimezone(tz)
        duration = end_dt_local - start_dt_local

        # Therapist offsets relative to event in LOCAL time
        th_start_offset = None
        th_end_offset = None
        if base.therapist_start:
            th_start_local = fields.Datetime.to_datetime(base.therapist_start).astimezone(tz)
            th_start_offset = th_start_local - start_dt_local
        if base.therapist_end:
            th_end_local = fields.Datetime.to_datetime(base.therapist_end).astimezone(tz)
            th_end_offset = th_end_local - end_dt_local

        start_date_local = start_dt_local.date()

        # start from the Monday of the base week (LOCAL calendar week)
        base_monday = start_date_local - timedelta(days=start_date_local.weekday())

        results = []
        occurrences_left = self.count if self.end_mode == 'count' else None
        until = self.until_date if self.end_mode == 'until' else None

        # Base local wall time components to preserve (hour/min/sec)
        base_h, base_m, base_s = start_dt_local.hour, start_dt_local.minute, start_dt_local.second

        def _localize_wall_time(y, m, d, h, mi, s):
            naive = datetime(y, m, d, h, mi, s)
            try:
                return tz.localize(naive, is_dst=None)
            except Exception:
                # Handle ambiguous/non-existent by choosing post-transition time
                try:
                    return tz.localize(naive, is_dst=True)
                except Exception:
                    return tz.localize(naive, is_dst=False)

        # Determine selected weekdays once
        weekdays = self._selected_weekdays()
        if not weekdays:
            return []

        week_index = 0
        while True:
            week_start = base_monday + timedelta(weeks=week_index * self.interval_weeks)
            # For each selected weekday build the candidate date
            for wd in weekdays:
                day_date = week_start + timedelta(days=wd)
                # Build local candidate at the SAME local wall time, then localize with DST awareness
                local_candidate_start = _localize_wall_time(day_date.year, day_date.month, day_date.day, base_h, base_m, base_s)
                # Convert to UTC naive for storage/comparison
                candidate_start_utc = local_candidate_start.astimezone(pytz.UTC)
                candidate_start = candidate_start_utc.replace(tzinfo=None)
                base_start_naive_utc = start_dt_utc.replace(tzinfo=None)
                # Only future after base start, exclude the base event itself
                if candidate_start <= base_start_naive_utc:
                    continue
                # End conditions
                if until and day_date > until:
                    return results
                # Compute end and therapist times in LOCAL, then convert to UTC naive
                local_candidate_end = local_candidate_start + duration
                if th_start_offset is not None:
                    local_th_start = local_candidate_start + th_start_offset
                    th_start_utc = local_th_start.astimezone(pytz.UTC).replace(tzinfo=None)
                else:
                    th_start_utc = False
                if th_end_offset is not None:
                    local_th_end = local_candidate_end + th_end_offset
                    th_end_utc = local_th_end.astimezone(pytz.UTC).replace(tzinfo=None)
                else:
                    th_end_utc = False
                results.append({
                    'date_start': candidate_start,
                    'date_end': local_candidate_end.astimezone(pytz.UTC).replace(tzinfo=None),
                    'therapist_start': th_start_utc,
                    'therapist_end': th_end_utc,
                })
                if occurrences_left is not None:
                    occurrences_left -= 1
                    if occurrences_left <= 0:
                        return results
            # If using until and progressed beyond, stop when next week would exceed far beyond reasonable range
            if until and (week_start > until + timedelta(weeks=260)):
                # safety stop ~5 years
                break
            week_index += 1
        return results

    def _recompute_preview(self):
        self.ensure_one()
        lines = [(5, 0, 0)]
        items = self._generate_occurrence_datetimes()
        for it in items:
            lines.append((0, 0, {
                'date_start': it['date_start'],
                'date_end': it['date_end'],
            }))
        self.write({'preview_line_ids': lines, 'preview_count': len(items)})

    @api.onchange('interval_weeks', 'by_mo', 'by_tu', 'by_we', 'by_th', 'by_fr', 'by_sa', 'by_su', 'end_mode', 'until_date', 'count')
    def _onchange_params(self):
        if self.base_event_id:
            self._recompute_preview()

    def action_preview(self):
        self._recompute_preview()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sports.event.recurrence.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_create_recurrences(self):
        self.ensure_one()
        items = self._generate_occurrence_datetimes()
        if not items:
            raise UserError('No occurrences to create. Adjust your settings.')
        base = self.base_event_id
        vals_template = {
            'name': base.name,
            'description': base.description,
            'event_type': base.event_type,
            # propagate all teams from the base event (many2many)
            'team_ids': [(6, 0, base.team_ids.ids)],
            'venue_id': base.venue_id.id if base.venue_id else False,
            'assigned_staff_ids': [(6, 0, base.assigned_staff_ids.ids)],
            'state': self.recurrence_state or 'confirmed',
        }
        Event = self.env['sports.event']
        created = Event
        for it in items:
            vals = dict(vals_template)
            vals.update({
                'date_start': it['date_start'],
                'date_end': it['date_end'],
                'therapist_start': it.get('therapist_start') or False,
                'therapist_end': it.get('therapist_end') or False,
            })
            created |= Event.create(vals)
        # Return to list/calendar filtered on team with newly created ones visible
        return {'type': 'ir.actions.act_window_close'}
