from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64


class InjuryDocument(models.Model):
    _name = 'sports.injury.document'
    _description = 'Injury Document'
    _order = 'create_date desc, id desc'
    
    name = fields.Char(string='Name', required=True)
    injury_id = fields.Many2one('sports.patient.injury', string='Injury', required=True, ondelete='cascade')
    patient_id = fields.Many2one('sports.patient', string='Patient', related='injury_id.patient_id', store=True)
    description = fields.Text(string='Description')
    file_content = fields.Binary(string='File Content', required=True, attachment=False)
    file_name = fields.Char(string='File Name')
    file_size = fields.Integer(string='File Size', compute='_compute_file_size', store=True)
    category = fields.Selection([
        ('medical', 'Medical Report'),
        ('xray', 'X-Ray'),
        ('mri', 'MRI'),
        ('prescription', 'Prescription'),
        ('other', 'Other'),
    ], string='Category', default='other', required=True)
    created_by_id = fields.Many2one('res.users', string='Uploaded By', default=lambda self: self.env.user, required=True)
    create_date = fields.Datetime(string='Upload Date')
    
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
