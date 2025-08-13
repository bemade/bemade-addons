from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64


class InjuryDocument(models.Model):
    _name = 'sports.injury.document'
    _description = 'Injury Document'
    _order = 'create_date desc, id desc'
    
    name = fields.Char(string='Name', required=True)
    # Refactor: documents are tied to a patient with optional injury linkage
    patient_id = fields.Many2one('sports.patient', string='Patient', required=True, ondelete='cascade', index=True)
    injury_id = fields.Many2one('sports.patient.injury', string='Injury', required=False, ondelete='cascade', index=True)
    description = fields.Text(string='Description')
    file_content = fields.Binary(string='File Content', required=True, attachment=False)
    file_name = fields.Char(string='File Name')
    file_size = fields.Integer(string='File Size', compute='_compute_file_size', store=True)
    # Note: 'xray' and 'mri' kept for backward compatibility; displayed as 'Medical Imaging'
    category = fields.Selection([
        ('medical', 'Medical'),
        ('medical_imaging', 'Medical Imaging'),
        ('xray', 'Medical Imaging'),  # deprecated
        ('mri', 'Medical Imaging'),   # deprecated
        ('prescription', 'Prescription'),
        ('other', 'Other'),
    ], string='Category', default='other', required=True)
    created_by_id = fields.Many2one('res.users', string='Uploaded By', default=lambda self: self.env.user, required=True)
    create_date = fields.Datetime(string='Upload Date')
    
    @api.model_create_multi
    def create(self, vals_list):
        """Ensure backward compatibility: if an injury is provided but patient is missing,
        set patient_id from the injury's patient."""
        for vals in vals_list:
            if not vals.get('patient_id') and vals.get('injury_id'):
                injury = self.env['sports.patient.injury'].browse(vals['injury_id'])
                vals['patient_id'] = injury.patient_id.id
        return super().create(vals_list)

    @api.onchange('injury_id')
    def _onchange_injury_id_sync_patient(self):
        """When selecting an injury, auto-set patient to the injury's patient."""
        for rec in self:
            if rec.injury_id:
                rec.patient_id = rec.injury_id.patient_id
    
    @api.constrains('injury_id', 'patient_id')
    def _check_injury_belongs_to_patient(self):
        """Ensure the selected injury belongs to the chosen patient."""
        for rec in self:
            if rec.injury_id and rec.patient_id and rec.injury_id.patient_id != rec.patient_id:
                raise ValidationError(_('The injury must belong to the selected patient.'))
    
    @api.depends('file_content')
    def _compute_file_size(self):
        """Compute the file size in bytes"""
        for record in self:
            if record.file_content:
                try:
                    record.file_size = len(base64.b64decode(record.file_content))
                except Exception:
                    record.file_size = 0
            else:
                record.file_size = 0
                
    @api.constrains('file_content')
    def _check_file_size(self):
        """Ensure document file size is within limits"""
        max_size = 10 * 1024 * 1024  # 10 MB
        for record in self:
            if record.file_size > max_size:
                raise ValidationError(_('Document file size cannot exceed 10 MB.'))
