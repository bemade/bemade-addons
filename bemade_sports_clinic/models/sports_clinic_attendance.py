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

UNREGISTERED KIOSK SIGN-INS (#1418)
-----------------------------------
A kiosk sign-in that matches NO patient is still queued: the row carries the
typed first name / last name / date of birth (``kiosk_*`` fields), no
``patient_id``, ``state='arrived'``, ``source='kiosk'`` and
``needs_confirmation``. It is the ONLY shape of row without a patient (see
``_check_patient_or_kiosk``), it is de-duplicated per clinic on the normalized
``kiosk_name_key``, and it is resolved by the therapist on the worklist:
``action_link_patient`` (pick a file — merging into that patient's existing
row if any), ``action_create_patient`` (one click: the file is created from
the typed data on a clinic team, then linked) or removed. Unresolved rows are
purged by ``_cron_purge_unregistered_kiosk_rows`` some days after the clinic
(``bemade_sports_clinic.kiosk_unregistered_retention_days``, default 7,
``0`` = never). Law 25: the typed identity is the only PHI on the row, it
lives only until resolved / removed / purged, and the audit notes on the
clinic's chatter carry ids only.

Not a tracked record: no ``mail.thread``. A worklist row is scaffolding for the
visit, and the clinical record of what happened is the treatment note.
"""
import logging
from datetime import timedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Ordered: index in this list IS the progression, so a later state implies
# every earlier one has happened (which is what the stamping below relies on).
ATTENDANCE_STATES = [
    ('expected', 'Expected'),
    ('arrived', 'Arrived'),
    ('seen', 'Seen'),
]

# Gap between consecutive rows, so a future "insert between" needs no rewrite.
SEQUENCE_STEP = 10

# #1418: longest typed kiosk value kept (the kiosk form caps at 80; the
# server must not trust that).
KIOSK_TYPED_MAXLEN = 80


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
        # #1418: empty on an unregistered kiosk sign-in (and ONLY there —
        # see _check_patient_or_kiosk).
        required=False,
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
        ATTENDANCE_STATES + [('no_show', 'No-show'), ('unregistered', 'Unregistered')],
        string='Outcome',
        compute='_compute_status_display',
        store=True,
        index=True,
        help="One axis for the report: the attendance status, No-show once "
             "the cron recorded it, or Unregistered for a kiosk sign-in that "
             "matched no patient file (#1418) — kept out of the other buckets.",
    )

    # ------------------------------------------------------------------
    # #1397 kiosk — who created the row, and whether the TP must confirm it
    # ------------------------------------------------------------------
    source = fields.Selection(
        [('tp', 'Therapist'), ('kiosk', 'Kiosk')],
        string='Source',
        default='tp',
        required=True,
        index=True,
        help="Therapist: put on the worklist from the clinic page. Kiosk: "
             "the patient signed themselves in on the clinic iPad.",
    )
    needs_confirmation = fields.Boolean(
        string='To Confirm',
        default=False,
        help="Kiosk sign-in matched on the name alone because the patient's "
             "file has no date of birth. The therapist confirms the identity "
             "(and can fill in the date of birth on the file).",
    )

    # ------------------------------------------------------------------
    # #1418 unregistered kiosk sign-in — the typed identity, until resolved
    # ------------------------------------------------------------------
    kiosk_first_name = fields.Char(
        string='Typed First Name',
        help="First name typed at the kiosk when no patient file matched. "
             "Cleared when the row is linked to a file; purged with the row.",
    )
    kiosk_last_name = fields.Char(
        string='Typed Last Name',
        help="Last name typed at the kiosk when no patient file matched.",
    )
    kiosk_date_of_birth = fields.Date(
        string='Typed Date of Birth',
        help="Date of birth typed at the kiosk when no patient file matched.",
    )
    kiosk_name_key = fields.Char(
        string='Typed Identity Key',
        compute='_compute_kiosk_name_key',
        store=True,
        index=True,
        help="Normalized « first|last|dob » of the typed identity, empty on "
             "linked rows — what de-duplicates a re-typed sign-in per clinic.",
    )
    is_unregistered = fields.Boolean(
        string='Unregistered',
        compute='_compute_is_unregistered',
        store=True,
        index=True,
        help="A kiosk sign-in that matched no patient file — to be linked, "
             "created or removed by the therapist.",
    )

    _unique_patient_per_clinic = models.Constraint(
        'unique(event_id, patient_id)',
        "This patient is already on this clinic's worklist.",
    )
    # NULL key on linked rows keeps this inert there (SQL UNIQUE ignores NULLs).
    _unique_kiosk_identity_per_clinic = models.Constraint(
        'unique(event_id, kiosk_name_key)',
        "This sign-in is already queued on this clinic's worklist.",
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

    @api.depends('state', 'no_show', 'patient_id')
    def _compute_status_display(self):
        for record in self:
            if not record.patient_id:
                record.status_display = 'unregistered'
            elif record.no_show and record.state == 'expected':
                record.status_display = 'no_show'
            else:
                record.status_display = record.state

    @api.model
    def _kiosk_name_key(self, first_name, last_name, date_of_birth):
        """The de-duplication key of a typed identity: normalized like the
        kiosk match (accents, case, hyphens, spacing) plus the ISO date of
        birth — so « kim kiosk » and « Kim  KIOSK » on the same day are ONE
        queued row. Empty when either name is empty."""
        Patient = self.env['sports.patient']
        first = Patient._kiosk_normalize(first_name)
        last = Patient._kiosk_normalize(last_name)
        if not first or not last:
            return False
        dob = fields.Date.to_date(date_of_birth) if date_of_birth else None
        return '%s|%s|%s' % (first, last, dob.isoformat() if dob else '')

    @api.depends('patient_id', 'kiosk_first_name', 'kiosk_last_name',
                 'kiosk_date_of_birth')
    def _compute_kiosk_name_key(self):
        for record in self:
            record.kiosk_name_key = False if record.patient_id else self._kiosk_name_key(
                record.kiosk_first_name, record.kiosk_last_name,
                record.kiosk_date_of_birth)

    @api.depends('patient_id', 'source')
    def _compute_is_unregistered(self):
        for record in self:
            record.is_unregistered = bool(
                record.source == 'kiosk' and not record.patient_id)

    @api.constrains('patient_id', 'source', 'kiosk_first_name', 'kiosk_last_name')
    def _check_patient_or_kiosk(self):
        """The ONLY row without a patient is an unregistered kiosk sign-in
        carrying a typed first AND last name."""
        for record in self:
            if record.patient_id:
                continue
            if not (record.source == 'kiosk'
                    and (record.kiosk_first_name or '').strip()
                    and (record.kiosk_last_name or '').strip()):
                raise ValidationError(_(
                    "A worklist row needs a patient, unless it is a kiosk "
                    "sign-in carrying the typed first and last name."))

    def _kiosk_display_name(self):
        """« First Last » as typed at the kiosk (unregistered rows)."""
        self.ensure_one()
        return ' '.join(part for part in (
            (self.kiosk_first_name or '').strip(),
            (self.kiosk_last_name or '').strip()) if part)

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
    # #1397 — kiosk sign-in (the second writer)
    # ------------------------------------------------------------------
    def action_confirm(self):
        """The therapist vouches for a name-only kiosk match."""
        return self.write({'needs_confirmation': False})

    @api.model
    def _kiosk_sign_in(self, event, first_name, last_name, date_of_birth):
        """Self sign-in at the clinic kiosk. Called with a VERIFIED clinic
        only (``sports.event._kiosk_verify``), under sudo().

        :return: ``(outcome, patient)`` with outcome one of
            ``'ok'``        row created (or the Expected row flipped) -> Arrived,
            ``'duplicate'`` already Arrived / Seen on this clinic (no 2nd row);
            ``patient`` is the matched patient — the page shows its FIRST NAME
            only — or EMPTY when the sign-in matched no file (#1418): the
            typed identity is then queued as an unregistered row (same
            outcomes, so the kiosk answers exactly like a normal sign-in and
            a re-typed identity reuses its row); the caller greets with the
            typed first name and still counts the attempt as a miss for the
            rate limiter. The log lines carry ids only.
        """
        event = event.sudo()
        Patient = self.env['sports.patient'].sudo()
        patient, flagged = Patient._kiosk_match(
            first_name, last_name, date_of_birth, event._kiosk_patient_scope())
        if not patient:
            return self._kiosk_queue_unregistered(
                event, first_name, last_name, date_of_birth), Patient.browse()
        Attendance = self.sudo()
        row = Attendance.search([
            ('event_id', '=', event.id), ('patient_id', '=', patient.id)], limit=1)
        if row and row.state in ('arrived', 'seen'):
            _logger.info("clinic kiosk: event %s sign-in: duplicate (attendance %s)",
                         event.id, row.id)
            return 'duplicate', patient
        if row:
            # Pre-listed by the therapist: the kiosk only flips the state
            # (the model stamps arrived_at); the row keeps its TP source.
            row.write({'state': 'arrived', 'needs_confirmation': flagged})
        else:
            row = Attendance.create({
                'event_id': event.id,
                'patient_id': patient.id,
                'state': 'arrived',
                'source': 'kiosk',
                'needs_confirmation': flagged,
            })
        _logger.info("clinic kiosk: event %s sign-in: arrived (attendance %s%s)",
                     event.id, row.id, ', to confirm' if flagged else '')
        return 'ok', patient

    # ------------------------------------------------------------------
    # #1418 — unregistered kiosk sign-ins: queue, resolve, purge
    # ------------------------------------------------------------------
    @api.model
    def _kiosk_queue_unregistered(self, event, first_name, last_name, date_of_birth):
        """No file matched: queue (or re-find) the unregistered row for this
        typed identity on this clinic. Returns the kiosk outcome — ``'ok'``
        the first time, ``'duplicate'`` on a re-type — mirroring a normal
        sign-in so the answer never tells a known name from an unknown one.
        """
        Attendance = self.sudo()
        first = ' '.join((first_name or '').split())[:KIOSK_TYPED_MAXLEN]
        last = ' '.join((last_name or '').split())[:KIOSK_TYPED_MAXLEN]
        dob = fields.Date.to_date(date_of_birth) if date_of_birth else False
        key = self._kiosk_name_key(first, last, dob)
        row = Attendance.search([
            ('event_id', '=', event.id), ('patient_id', '=', False),
            ('kiosk_name_key', '=', key)], limit=1) if key else Attendance.browse()
        if row:
            _logger.info("clinic kiosk: event %s sign-in: no match, already queued "
                         "(attendance %s)", event.id, row.id)
            return 'duplicate'
        row = Attendance.create({
            'event_id': event.id,
            'state': 'arrived',
            'source': 'kiosk',
            'needs_confirmation': True,
            'kiosk_first_name': first,
            'kiosk_last_name': last,
            'kiosk_date_of_birth': dob,
        })
        _logger.info("clinic kiosk: event %s sign-in: no match, queued unregistered "
                     "(attendance %s)", event.id, row.id)
        return 'ok'

    def _audit_unregistered(self, action, patient=None):
        """Staff-only note on the CLINIC's chatter — ids only, never the typed
        identity (same style as the kiosk open / revoke notes)."""
        self.ensure_one()
        event = self.event_id.sudo()
        if action == 'link':
            body = _("Unregistered kiosk sign-in #%(row)s linked to patient #%(patient)s (clinic #%(event)s).",
                     row=self.id, patient=patient.id if patient else 0, event=event.id)
        elif action == 'create':
            body = _("Unregistered kiosk sign-in #%(row)s: patient #%(patient)s created and linked (clinic #%(event)s).",
                     row=self.id, patient=patient.id if patient else 0, event=event.id)
        else:
            body = _("Unregistered kiosk sign-in #%(row)s removed (clinic #%(event)s).",
                     row=self.id, event=event.id)
        event.message_post(body=body, message_type='comment',
                           subtype_xmlid='mail.mt_note')
        _logger.info("clinic kiosk: event %s unregistered row %s %s by user %s",
                     event.id, self.id, action, self.env.user.id)

    def action_link_patient(self, patient, audit=True):
        """Resolve an unregistered row to ``patient``'s file.

        If that patient already has a row on this clinic, MERGE into it: the
        existing row becomes (at least) Arrived, keeps the earlier arrival
        stamp and its own position, and the unregistered row is dropped.
        Otherwise this row takes the patient (team defaulted as on create) and
        the typed identity is cleared. Returns the surviving row.
        """
        self.ensure_one()
        if self.patient_id:
            raise ValidationError(_("This worklist row is already linked to a patient."))
        patient = patient.sudo()
        if not patient:
            raise ValidationError(_("Pick a patient to link the sign-in to."))
        Attendance = self.sudo()
        existing = Attendance.search([
            ('event_id', '=', self.event_id.id), ('patient_id', '=', patient.id),
            ('id', '!=', self.id)], limit=1)
        if existing:
            vals = {}
            if existing.state == 'expected':
                # Arrived when the kiosk said so — not "now".
                vals.update(state='arrived', arrived_at=self.arrived_at or fields.Datetime.now())
            elif (self.arrived_at and existing.arrived_at
                  and self.arrived_at < existing.arrived_at):
                vals['arrived_at'] = self.arrived_at
            if vals:
                existing.write(vals)
            if audit:
                self._audit_unregistered('link', patient)
            Attendance.browse(self.id).unlink()
            return existing
        self.write({
            'patient_id': patient.id,
            'kiosk_first_name': False,
            'kiosk_last_name': False,
            'kiosk_date_of_birth': False,
            'needs_confirmation': False,
            'team_id': self._default_team_id(self.event_id.id, patient.id),
        })
        if audit:
            self._audit_unregistered('link', patient)
        return self

    def action_create_patient(self, team):
        """One-click resolution: create the patient file from the typed
        identity on ``team`` (one of the clinic's teams — the caller checks
        the therapist staffs it), then link. Returns ``(row, patient)``."""
        self.ensure_one()
        if self.patient_id:
            raise ValidationError(_("This worklist row is already linked to a patient."))
        if not team:
            raise ValidationError(_("Pick the team the new player belongs to."))
        patient = self.env['sports.patient']._create_portal_patient({
            'first_name': (self.kiosk_first_name or '').strip(),
            'last_name': (self.kiosk_last_name or '').strip(),
            'date_of_birth': self.kiosk_date_of_birth or False,
            'team_ids': [Command.set([team.id])],
        })
        self._audit_unregistered('create', patient)
        row = self.action_link_patient(patient, audit=False)
        return row, patient

    @api.model
    def _kiosk_unregistered_retention_days(self):
        """Days after the clinic's end before an unresolved row is purged
        (``bemade_sports_clinic.kiosk_unregistered_retention_days``, default
        7). ``0`` (or less, or garbage) = never."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'bemade_sports_clinic.kiosk_unregistered_retention_days', '7')
        try:
            return max(int(str(raw).strip()), 0)
        except (TypeError, ValueError):
            return 7

    @api.model
    def _cron_purge_unregistered_kiosk_rows(self):
        """Daily: drop unresolved unregistered rows whose clinic ended more
        than the retention window ago — the typed identity is the only PHI
        on them and must not outlive its usefulness. Linked rows are never
        touched (they carry no typed identity any more). ids only in the log."""
        days = self._kiosk_unregistered_retention_days()
        if not days:
            _logger.info("clinic kiosk: unregistered purge disabled (retention 0)")
            return True
        cutoff = fields.Datetime.now() - timedelta(days=days)
        rows = self.sudo().search([
            ('patient_id', '=', False),
            '|', ('event_id.date_end', '<', cutoff),
            '&', ('event_id.date_end', '=', False), ('event_id.date_start', '<', cutoff),
        ])
        if rows:
            _logger.info("clinic kiosk: purging %s unregistered row(s) older than %s day(s): %s",
                         len(rows), days, rows.ids)
            rows.unlink()
        return True

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
            # #1418: an unregistered kiosk sign-in is never a no-show.
            ('patient_id', '!=', False),
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
