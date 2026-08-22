from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.misc import format_date


# Task 1413: the fields a portal edit may touch — the write() guard below only
# fires for these (a portal TP may never rewrite someone else's clinical
# content), so technical writes on other columns stay unaffected.
PORTAL_EDIT_FIELDS = ('note', 'date', 'injury_id', 'patient_id', 'user_id', 'event_id')


class TreatmentNote(models.Model):
    _name = 'sports.treatment.note'
    _description = 'Treatment Note'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    patient_id = fields.Many2one('sports.patient', string='Patient', required=True, ondelete='cascade', index=True, tracking=True)
    injury_id = fields.Many2one('sports.patient.injury', string='Injury', required=False, ondelete='cascade', index=True, tracking=True)
    # Task 1398: where the note was taken. Optional by design — notes captured
    # from the injury or player pages have no event, and must keep working
    # exactly as before. Set by the clinic worklist's docked capture form so a
    # note can be attributed to the clinic it was written at (and so #1399 can
    # later report notes-per-clinic). ondelete='set null': deleting an event
    # must never delete the clinical record written at it.
    event_id = fields.Many2one(
        'sports.event', string='Event', required=False, ondelete='set null',
        index=True, tracking=True,
        help="The event — typically a clinic — this note was captured at. "
             "Empty for notes written from the injury or player pages.")
    note = fields.Text(string='Note', required=True, tracking=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Added By', default=lambda self: self.env.user, required=True, tracking=True)
    note_type = fields.Selection([
        ('general', 'General Note'),
        ('injury', 'Injury-specific')
    ], string='Note Type', compute='_compute_note_type', store=True)
    author_initials = fields.Char(
        string='Author Initials',
        compute='_compute_author_initials',
        help="Initials of the note author, for compact list/portal display.",
    )
    # Task 1413: « modified on <date> by <initials> » for the portal rows —
    # empty until the note was actually edited after its creation.
    modified_label = fields.Char(
        string='Modified Label', compute='_compute_modified_label',
        help="Portal caption shown under an edited note; empty for a note "
             "that was never edited after being added.")
    modified_by_name = fields.Char(
        string='Modified By', compute='_compute_modified_label')

    @api.depends('injury_id')
    def _compute_note_type(self):
        """Determine whether this is a general note or injury-specific"""
        for record in self:
            record.note_type = 'injury' if record.injury_id else 'general'

    @staticmethod
    def _initials(name):
        """First + last token of ``name``, uppercased ('' when empty)."""
        tokens = (name or '').split()
        if not tokens:
            return ''
        if len(tokens) == 1:
            return tokens[0][0].upper()
        return (tokens[0][0] + tokens[-1][0]).upper()

    @api.depends('user_id', 'user_id.name')
    def _compute_author_initials(self):
        """Derive the author's initials (first + last token, uppercased)."""
        for record in self:
            record.author_initials = self._initials(record.user_id.name)

    def _is_modified(self):
        """True when the note was written to after its creation (task 1413).

        Same-transaction writes share the creation timestamp (cr.now() is
        cached per transaction), so a freshly created note never counts as
        modified; the one-second slack covers sub-second technical writes."""
        self.ensure_one()
        return bool(
            self.write_date and self.create_date
            and self.write_date > self.create_date + timedelta(seconds=1))

    @api.depends('write_date', 'create_date', 'write_uid', 'write_uid.name')
    def _compute_modified_label(self):
        for record in self:
            if not record._is_modified():
                record.modified_label = ''
                record.modified_by_name = ''
                continue
            editor = record.sudo().write_uid
            when = fields.Date.context_today(record, timestamp=record.write_date)
            record.modified_by_name = editor.name or ''
            record.modified_label = _(
                'modified on %(date)s by %(initials)s',
                date=format_date(record.env, when),
                initials=self._initials(editor.name))

    # ------------------------------------------------------------------
    # Task 1413: portal edit permission — author or clinic admin
    # ------------------------------------------------------------------
    def _can_portal_edit(self, user=None):
        """May ``user`` (default: the current user) edit this note from the
        portal? The author (``user_id``) may, and so may a clinic
        administrator (internal Sports Clinic admin group or base.group_system).
        Evaluated with sudo on the record: the caller decides whether the user
        may SEE the note (patient access check) — this only says who may
        change it."""
        self.ensure_one()
        user = (user or self.env.user).sudo()
        if (user.has_group('bemade_sports_clinic.group_sports_clinic_admin')
                or user.has_group('base.group_system')):
            return True
        return self.sudo().user_id == user

    def write(self, vals):
        """Defence in depth for the portal edit route (task 1413): a portal
        user — sudo or not — may only rewrite the clinical content of notes
        they authored (or, as a clinic admin, any note). Internal users keep
        the ACL / record-rule behaviour they have today."""
        if vals and any(f in vals for f in PORTAL_EDIT_FIELDS):
            user = self.env.user
            if user._is_portal():
                for record in self:
                    if not record._can_portal_edit(user):
                        raise AccessError(_(
                            'Only the author of a treatment note (or an '
                            'administrator) can edit it.'))
        return super().write(vals)
    
    @api.constrains('note')
    def _check_note_content(self):
        """Ensure treatment notes have content"""
        for record in self:
            if not record.note or not record.note.strip():
                raise ValidationError(_('Treatment note cannot be empty.'))
    
    @api.constrains('injury_id', 'patient_id')
    def _check_injury_patient_match(self):
        """Ensure the injury belongs to the selected patient"""
        for record in self:
            if record.injury_id and record.injury_id.patient_id != record.patient_id:
                raise ValidationError(_('The injury must belong to the selected patient.'))
