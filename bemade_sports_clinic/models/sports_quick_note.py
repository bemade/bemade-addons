"""Quick notes — personal, on-the-go scratch capture for treatment professionals.

A quick note is deliberately NOT a clinical record: no chatter, no workflow, no
reporting, and it is never surfaced on the dashboard, the digest, the morning
briefing or the urgent notifications. It is a note to self that its owner drains
later from the portal inbox at ``/my/notes``.

The model carries ``mail.activity.mixin`` purely so the stale-note escalation cron
can hang a reminder activity on the record.

``mail.thread`` comes along with it, and NOT because a scratch note wants a
conversation: ``mail.activity`` calls ``message_subscribe`` on the related record
when an activity is created, and ``message_post_with_source`` when it is marked
done, both of which live on ``mail.thread``. Every core model carrying
``mail.activity.mixin`` also carries ``mail.thread`` for exactly this reason —
without it the nudge cannot be raised, let alone completed. The design intent the
plan was protecting is upheld another way: no chatter widget on any view, no
``tracking=True`` on any field, and no surfacing of notes on the dashboard,
digest, briefing or urgent notifications.
"""
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Number of days after which an *active* quick note is considered stale and the
# escalation cron nudges its owner (and the clinic administrators).
STALE_DAYS_PARAM = 'bemade_sports_clinic.quick_note_stale_days'
STALE_DAYS_DEFAULT = 365


class SportsQuickNote(models.Model):
    _name = 'sports.quick.note'
    _description = 'Quick Note'
    # mail.thread is a framework requirement of mail.activity, not a feature —
    # see the module docstring. No chatter is rendered anywhere.
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # Newest first: the inbox is drained top-down and capture is the hot path.
    _order = 'create_date desc, id desc'

    note = fields.Text(string='Note', required=True)
    user_id = fields.Many2one(
        'res.users',
        string='Owner',
        required=True,
        index=True,
        ondelete='cascade',
        default=lambda self: self.env.user,
        help="The person who captured this note. Quick notes are personal: only "
             "their owner (and a clinic administrator) can see them.",
    )
    # Dismissed / handled == archived. One concept, deliberately not a state
    # machine — a quick note is either still to drain, or it is done.
    active = fields.Boolean(string='Active', default=True)

    # Optional links. NONE of these is required: the whole point is that a note
    # can be captured in seconds with nothing but its text.
    team_id = fields.Many2one('sports.team', string='Team', ondelete='set null')
    patient_id = fields.Many2one('sports.patient', string='Player', ondelete='set null')
    injury_id = fields.Many2one('sports.patient.injury', string='Injury', ondelete='set null')
    event_id = fields.Many2one('sports.event', string='Event', ondelete='set null')

    @api.depends('note')
    def _compute_display_name(self):
        """Short one-line label — what a linked mail.activity shows as res_name."""
        for record in self:
            text = ' '.join((record.note or '').split())
            record.display_name = (text[:47] + '...') if len(text) > 50 else (text or _('Quick Note'))

    @api.constrains('note')
    def _check_note_content(self):
        """A quick note with no content is not a note (mirrors sports.treatment.note)."""
        for record in self:
            if not record.note or not record.note.strip():
                raise ValidationError(_('A quick note cannot be empty.'))

    def write(self, vals):
        """Dismissing a note clears any reminder the escalation raised on it.

        The stale nudge literally says "handle it or dismiss it"; leaving the
        activity alive after the user did exactly that would be nagging about a
        note that is no longer in anyone's inbox.
        """
        res = super().write(vals)
        if vals.get('active') is False:
            self.sudo().activity_ids.unlink()
        return res

    # ------------------------------------------------------------------
    # Stale-note escalation
    # ------------------------------------------------------------------
    @api.model
    def _stale_note_days(self):
        """Configured staleness threshold in days, falling back to the default."""
        raw = self.env['ir.config_parameter'].sudo().get_param(STALE_DAYS_PARAM)
        try:
            days = int(raw)
        except (TypeError, ValueError):
            return STALE_DAYS_DEFAULT
        return days if days > 0 else STALE_DAYS_DEFAULT

    @api.model
    def _cron_escalate_stale_notes(self):
        """Nudge owners (and clinic admins) about quick notes left to rot.

        Owner decision: the system never auto-purges a note — users delete their
        own. All this does is raise a reminder.

        Two volume guards keep a year-old backlog from turning into an activity
        storm, and both are idempotent so repeated cron runs raise nothing new:

        * the OWNER gets one activity per stale note (they are the person who
          can actually act on each one);
        * each ADMIN gets ONE summarising activity per owner-with-stale-notes,
          hung on that owner's oldest stale note, not one per note.

        Dedupe follows ``sports.patient._cron_handle_pending_removals``: look for
        an existing open activity before creating. The escalation is the only
        producer of activities on this model, so keying the search on
        (res_model, res_id, user_id, activity_type_id) is sufficient.
        """
        cutoff = fields.Datetime.now() - timedelta(days=self._stale_note_days())
        Note = self.sudo()
        stale = Note.search([('active', '=', True), ('create_date', '<=', cutoff)])
        if not stale:
            return

        activity_type = self.env.ref('mail.mail_activity_data_todo')
        model_id = self.env['ir.model']._get(self._name).id
        today = fields.Date.today()
        Activity = self.env['mail.activity'].sudo()
        admins = self.env.ref(
            'bemade_sports_clinic.group_sports_clinic_admin'
        ).sudo().all_user_ids.filtered('active')

        def _already_nudged(res_ids, user):
            return bool(Activity.search([
                ('res_model', '=', self._name),
                ('res_id', 'in', res_ids),
                ('user_id', '=', user.id),
                ('activity_type_id', '=', activity_type.id),
            ], limit=1))

        for owner, notes in stale.grouped('user_id').items():
            if not owner or not owner.active:
                continue
            # --- the owner: one reminder per note still sitting in their inbox.
            for note in notes:
                if _already_nudged(note.ids, owner):
                    continue
                Activity.create({
                    'activity_type_id': activity_type.id,
                    'summary': _('Stale quick note'),
                    'note': _(
                        'This quick note has been sitting in your inbox for more than '
                        '%(days)s days. Handle it or dismiss it.',
                        days=self._stale_note_days(),
                    ),
                    'user_id': owner.id,
                    'res_id': note.id,
                    'res_model_id': model_id,
                    'date_deadline': today,
                })
            # --- the admins: ONE summarising reminder per owner, not per note.
            oldest = notes.sorted('create_date')[0]
            for admin in admins:
                if admin == owner:
                    continue  # already nudged above, per note
                if _already_nudged(notes.ids, admin):
                    continue
                Activity.create({
                    'activity_type_id': activity_type.id,
                    'summary': _('Stale quick notes to review'),
                    'note': _(
                        '%(user)s has %(count)s quick note(s) older than %(days)s days '
                        'still waiting in their inbox.',
                        user=owner.name,
                        count=len(notes),
                        days=self._stale_note_days(),
                    ),
                    'user_id': admin.id,
                    'res_id': oldest.id,
                    'res_model_id': model_id,
                    'date_deadline': today,
                })
