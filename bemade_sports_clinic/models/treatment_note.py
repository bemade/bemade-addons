from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TreatmentNote(models.Model):
    _name = 'sports.treatment.note'
    _description = 'Treatment Note'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    patient_id = fields.Many2one('sports.patient', string='Patient', required=True, ondelete='cascade', index=True, tracking=True)
    injury_id = fields.Many2one('sports.patient.injury', string='Injury', required=False, ondelete='cascade', index=True, tracking=True)
    note = fields.Text(string='Note', required=True, tracking=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Added By', default=lambda self: self.env.user, required=True, tracking=True)
    note_type = fields.Selection([
        ('general', 'General Note'),
        ('injury', 'Injury-specific')
    ], string='Note Type', compute='_compute_note_type', store=True)
    
    @api.depends('injury_id')
    def _compute_note_type(self):
        """Determine whether this is a general note or injury-specific"""
        for record in self:
            record.note_type = 'injury' if record.injury_id else 'general'
    
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
