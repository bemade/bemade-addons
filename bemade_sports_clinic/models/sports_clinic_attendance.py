"""Clinic attendance — the worklist row behind /my/clinic/<id> (task 1398).

This is the FIRST and only patient <-> event link in the addon: before this
model the only path from a clinic to the people attending it was transitive
(``event.team_ids.patient_ids``), i.e. the whole roster of every team the
clinic serves. A clinic worklist is a much smaller, ordered, stateful thing.

Deliberately shaped for MORE THAN ONE WRITER
--------------------------------------------
The therapist portal (this task) is the first writer. Two siblings follow:

* **#1397** (iPad sign-in kiosk) will write rows self-service — a patient
  signs themselves in and the row flips ``expected`` -> ``arrived``;
* **#1399** (clinic stats) will aggregate rows — attendance, no-shows,
  waiting time (``seen_at - arrived_at``), throughput.

So the lifecycle lives in ``create``/``write`` on the model, NOT in the
controller: whoever writes ``state`` gets the ``arrived_at`` / ``seen_at``
stamps for free, and the timestamps always agree with the state (moving a row
back clears the stamps it no longer earned). Same for ``_set_worklist_order``,
which is the single reorder primitive shared by the drag and the up/down
buttons.

NO-SHOW IS DERIVED, NOT A FOURTH STATE
--------------------------------------
A row still ``expected`` once the clinic has ended IS a no-show — see
``is_no_show``. There is deliberately no ``no_show`` selection value: nobody
has to remember to set it, it cannot go stale, and the portal needs no cron.

#1399 (clinic stats) adds the REPORTING shape on top, without changing that:

* ``no_show`` is the STORED twin of ``is_no_show``, set by the daily
  ``_cron_flag_no_shows`` (rows still Expected whose clinic has ended) and
  cleared the moment the row moves on to Arrived / Seen (or the clinic is
  moved back into the future). Stored so the pivot can group on it;
* ``status_display`` folds state + no_show into ONE groupable axis
  (expected / arrived / seen / no_show) — the pivot's column;
* ``clinic_date`` (local day), ``team_id`` (the patient's team for THIS
  clinic), ``event_team_ids`` / ``therapist_ids`` (mirrors of the clinic) and
  ``seen_by_id`` are the other axes. All stored, all computed in sudo: the
  event's fields are group-restricted and the dimensions must resolve for
  every reader allowed to see the row.

Not a tracked record: no ``mail.thread``. A worklist row is scaffolding for the
visit, and the clinical record of what happened is the treatment note.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Ordered: index in this list IS the progression, so a later state implies
# every earlier one has happened (which is what the stamping below relies on).
ATTENDANCE_STATES = [
    ('expected', 'Expected'),
    ('arrived', 'Arrived'),
    ('seen', 'Seen'),
]

# Gap between consecutive rows, so a future "insert between" needs no rewrite.
SEQUENCE_STEP = 10


class SportsClinicAttendance(models.Model):
    _name = 'sports.clinic.attendance'
    _description = 'Clinic Attendance'
    # The worklist IS an ordered list — the therapist decides who is next.
    _order = 'sequence, id'

    event_id = fields.Many2one(
        'sports.event',
        string='Clinic',
        required=True,
        ondelete='cascade',
        index=True,
        help="The clinic this patient is on the worklist for.",
    )
    patient_id = fields.Many2one(
        'sports.patient',
        string='Patient',
        required=True,
        ondelete='cascade',
        index=True,
    )
    state = fields.Selection(
        ATTENDANCE_STATES,
        # NOT 'Status': that msgid is already taken addon-wide (and translated
        # as the event's "Étape"). A worklist row has its own vocabulary.
        string='Attendance Status',
        default='expected',
        required=True,
        index=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=SEQUENCE_STEP,
        help="Position in the clinic worklist. The therapist reorders freely.",
    )
    arrived_at = fields.Datetime(
        string='Arrived At',
        readonly=True,
        help="Stamped the first time the row reaches Arrived (or Seen).",
    )
    seen_at = fields.Datetime(
        string='Seen At',
        readonly=True,
        help="Stamped the first time the row reaches Seen.",
    )
    is_no_show = fields.Boolean(
        string='No Show',
        compute='_compute_is_no_show',
        help="Derived, never stored: still Expected after the clinic ended.",
    )

    # ------------------------------------------------------------------
    # #1399 reporting dimensions — all stored, all groupable
    # ------------------------------------------------------------------
    clinic_date = fields.Date(
        string='Clinic Date',
        compute='_compute_clinic_date',
        store=True,
        index=True,
        help="Calendar day of the clinic in its local timezone — the month "
             "axis of the attendance report.",
    )
    # Related + stored: the pivot filters/groups on the clinic's teams and
    # therapists without a join through a group-restricted field. The related
    # target carries the event's portal groups, which these inherit.
    event_team_ids = fields.Many2many(
        related='event_id.team_ids',
        relation='sports_clinic_attendance_event_team_rel',
        column1='attendance_id',
        column2='team_id',
        string='Clinic Teams',
        store=True,
    )
    team_id = fields.Many2one(
        'sports.team',
        string='Team',
        index=True,
        ondelete='set null',
        help="The patient's team for this clinic: defaults to the patient's "
             "team among the clinic's teams, else the patient's first team. "
             "Editable when the default guesses wrong.",
    )
    therapist_ids = fields.Many2many(
        related='event_id.assigned_staff_ids',
        relation='sports_clinic_attendance_therapist_rel',
        column1='attendance_id',
        column2='user_id',
        string='Therapists',
        store=True,
    )
    seen_by_id = fields.Many2one(
        'res.users',
        string='Seen By',
        readonly=True,
        index=True,
        help="The user who first moved this row to Seen. Cleared if the row "
             "is moved back.",
    )
    no_show = fields.Boolean(
        string='Recorded No Show',
        readonly=True,
        default=False,
        index=True,
        help="Stored by the daily no-show cron: still Expected after the "
             "clinic ended. Cleared as soon as the row moves to Arrived or "
             "Seen. The live equivalent is the derived No Show flag.",
    )
    status_display = fields.Selection(
        ATTENDANCE_STATES + [('no_show', 'No-show')],
        string='Outcome',
        compute='_compute_status_display',
        store=True,
        index=True,
        help="One axis for the report: the attendance status, or No-show once "
             "the cron recorded it.",
    )

    _unique_patient_per_clinic = models.Constraint(
        'unique(event_id, patient_id)',
        "This patient is already on this clinic's worklist.",
    )

    # ------------------------------------------------------------------
    # computes / constraints
    # ------------------------------------------------------------------
    @api.depends('state', 'event_id.date_end', 'event_id.date_start')
    def _compute_is_no_show(self):
        """A row left Expected once the clinic is over.

        sudo() on the event: the date fields are group-restricted on
        sports.event, and this flag must still resolve for any reader allowed
        to see the attendance row itself.
        """
        now = fields.Datetime.now()
        for record in self:
            event = record.event_id.sudo()
            ended = event.date_end or event.date_start
            record.is_no_show = bool(
                record.state == 'expected' and ended and ended < now)

    @api.depends('event_id.date_start', 'event_id.team_ids')
    def _compute_clinic_date(self):
        """The clinic's LOCAL calendar day, resolved like the team digests
        (organization partner tz, else the default-tz parameter, else the
        company partner tz, else UTC) — never the reader's tz, because the
        value is stored."""
        Digest = self.env['sports.team.digest']
        for record in self:
            event = record.event_id.sudo()
            if not event.date_start:
                record.clinic_date = False
                continue
            tz_name = Digest._resolve_timezone(event.team_ids[:1])
            record.clinic_date = fields.Datetime.context_timestamp(
                record.with_context(tz=tz_name), event.date_start).date()

    @api.depends('state', 'no_show')
    def _compute_status_display(self):
        for record in self:
            record.status_display = (
                'no_show' if record.no_show and record.state == 'expected'
                else record.state)

    @api.constrains('event_id')
    def _check_event_is_clinic(self):
        """Attendance is a clinic concept — refuse it on games/practices.

        sudo(): event_type is group-restricted, and the constraint must hold
        regardless of who is writing (including the #1397 kiosk).
        """
        for record in self:
            if record.event_id.sudo().event_type != 'clinic':
                raise ValidationError(_(
                    "Attendance can only be recorded on a clinic event."))

    # ------------------------------------------------------------------
    # lifecycle — stamping lives here so EVERY writer gets it
    # ------------------------------------------------------------------
    def _next_sequence(self, event_id):
        """Append position for a new row on this clinic's worklist."""
        if not event_id:
            return SEQUENCE_STEP
        last = self.search(
            [('event_id', '=', int(event_id))],
            order='sequence desc, id desc', limit=1)
        return (last.sequence or 0) + SEQUENCE_STEP

    def _default_team_id(self, event_id, patient_id):
        """The patient's team for this clinic.

        First team of ``patient.team_ids`` that the clinic serves; else the
        patient's first team (a walk-in from another team still counts for
        their own team); else nothing. Writers may pass ``team_id`` to
        override, and the backend keeps it editable.
        """
        if not (event_id and patient_id):
            return False
        patient = self.env['sports.patient'].sudo().browse(int(patient_id))
        event = self.env['sports.event'].sudo().browse(int(event_id))
        on_clinic = patient.team_ids & event.team_ids
        team = on_clinic[:1] or patient.team_ids[:1]
        return team.id or False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('sequence'):
                vals['sequence'] = self._next_sequence(vals.get('event_id'))
            if 'team_id' not in vals:
                vals['team_id'] = self._default_team_id(
                    vals.get('event_id'), vals.get('patient_id'))
        records = super().create(vals_list)
        records._sync_state_timestamps()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals:
            self._sync_state_timestamps()
        return res

    def _sync_state_timestamps(self):
        """Keep arrived_at / seen_at consistent with the current state.

        Forward: stamp the first time a row reaches Arrived / Seen — never
        re-stamp, so a re-save does not move the clock.
        Backward: a row moved back loses the stamps it no longer earned, so a
        mis-tap is genuinely undone rather than leaving #1399 to average a
        waiting time that never happened.

        ``seen_by_id`` rides along with ``seen_at`` (stamped once, cleared on
        regression), and the stored ``no_show`` flag is dropped the moment a
        row leaves Expected — a late patient who is seen was not a no-show.
        """
        now = fields.Datetime.now()
        for record in self:
            stamp = {}
            if record.state == 'expected':
                if record.arrived_at:
                    stamp['arrived_at'] = False
                if record.seen_at:
                    stamp['seen_at'] = False
                if record.seen_by_id:
                    stamp['seen_by_id'] = False
            elif record.state == 'arrived':
                if not record.arrived_at:
                    stamp['arrived_at'] = now
                if record.seen_at:
                    stamp['seen_at'] = False
                if record.seen_by_id:
                    stamp['seen_by_id'] = False
            else:  # seen
                if not record.arrived_at:
                    stamp['arrived_at'] = now
                if not record.seen_at:
                    stamp['seen_at'] = now
                if not record.seen_by_id:
                    stamp['seen_by_id'] = self.env.user.id
            if record.state != 'expected' and record.no_show:
                stamp['no_show'] = False
            if stamp:
                super(SportsClinicAttendance, record).write(stamp)

    # ------------------------------------------------------------------
    # #1399 — the daily no-show cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_flag_no_shows(self):
        """Record no-shows: rows still Expected whose clinic has ended.

        Idempotent both ways — also UN-flags rows whose clinic was moved back
        into the future, so a rescheduled clinic does not keep phantom
        absences. Rows that moved on to Arrived / Seen were already cleared by
        ``_sync_state_timestamps`` at write time. sudo(): the event's dates
        are group-restricted and the cron user is root anyway.
        """
        now = fields.Datetime.now()
        Attendance = self.sudo()
        to_flag = Attendance.search([
            ('state', '=', 'expected'),
            ('no_show', '=', False),
            ('event_id.date_end', '<', now),
        ])
        to_flag.write({'no_show': True})
        to_clear = Attendance.search([
            ('no_show', '=', True),
            '|', ('state', '!=', 'expected'),
            ('event_id.date_end', '>=', now),
        ])
        to_clear.write({'no_show': False})
        return True

    # ------------------------------------------------------------------
    # reordering — ONE primitive, used by drag AND by the up/down buttons
    # ------------------------------------------------------------------
    def _set_worklist_order(self, ordered_ids):
        """Renumber ``sequence`` so ``self`` follows ``ordered_ids``.

        ``self`` is the whole worklist of one clinic. Ids not in ``self`` are
        ignored (a stale tab must not be able to reorder someone else's list);
        rows of ``self`` missing from ``ordered_ids`` keep their relative order
        at the end, so a row added in another tab is never silently dropped.

        Drag posts the full new order once, after the drop. The up/down buttons
        post a swap of two ids. Both land here.
        """
        by_id = {record.id: record for record in self}
        ordered = [by_id[rid] for rid in ordered_ids if rid in by_id]
        ordered_ids_seen = {record.id for record in ordered}
        rest = [record for record in self.sorted(lambda r: (r.sequence, r.id))
                if record.id not in ordered_ids_seen]
        for index, record in enumerate(ordered + rest, start=1):
            position = index * SEQUENCE_STEP
            if record.sequence != position:
                record.sequence = position
        return True

    def _move_in_worklist(self, direction):
        """Swap ``self`` (a single row) with its neighbour, up or down.

        The keyboard / no-JS / mobile reorder path. Expressed as a full
        reorder so there is exactly one place that assigns sequences.
        """
        self.ensure_one()
        siblings = self.search([('event_id', '=', self.event_id.id)])
        ordered = list(siblings.sorted(lambda r: (r.sequence, r.id)))
        try:
            index = ordered.index(self)
        except ValueError:
            return False
        target = index - 1 if direction == 'up' else index + 1
        if target < 0 or target >= len(ordered):
            return False  # already at the edge — a no-op, not an error
        ordered[index], ordered[target] = ordered[target], ordered[index]
        return siblings._set_worklist_order([record.id for record in ordered])
