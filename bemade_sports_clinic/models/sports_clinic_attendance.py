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
has to remember to set it, it cannot go stale, and it needs no cron. #1399
reads the same derivation for its stat (and can express it as a domain:
``[('state', '=', 'expected'), ('event_id.date_end', '<', now)]``).

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('sequence'):
                vals['sequence'] = self._next_sequence(vals.get('event_id'))
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
        """
        now = fields.Datetime.now()
        for record in self:
            stamp = {}
            if record.state == 'expected':
                if record.arrived_at:
                    stamp['arrived_at'] = False
                if record.seen_at:
                    stamp['seen_at'] = False
            elif record.state == 'arrived':
                if not record.arrived_at:
                    stamp['arrived_at'] = now
                if record.seen_at:
                    stamp['seen_at'] = False
            else:  # seen
                if not record.arrived_at:
                    stamp['arrived_at'] = now
                if not record.seen_at:
                    stamp['seen_at'] = now
            if stamp:
                super(SportsClinicAttendance, record).write(stamp)

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
