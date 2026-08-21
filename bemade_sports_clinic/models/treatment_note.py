from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


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

    @api.depends('injury_id')
    def _compute_note_type(self):
        """Determine whether this is a general note or injury-specific"""
        for record in self:
            record.note_type = 'injury' if record.injury_id else 'general'

    @api.depends('user_id', 'user_id.name')
    def _compute_author_initials(self):
        """Derive the author's initials (first + last token, uppercased)."""
        for record in self:
            tokens = (record.user_id.name or '').split()
            if not tokens:
                record.author_initials = ''
            elif len(tokens) == 1:
                record.author_initials = tokens[0][0].upper()
            else:
                record.author_initials = (tokens[0][0] + tokens[-1][0]).upper()
    
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
