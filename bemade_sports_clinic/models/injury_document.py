from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64

from markupsafe import Markup


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
    # Task 1432: a portal « Delete » archives the document (a clinic
    # administrator restores it from the backend); archived documents leave
    # every portal list, count and download.
    active = fields.Boolean(default=True)

    def _sc_can_manage(self, user=None):
        """Task 1432 (owner decision 2026-10-31): who may edit / delete
        (archive) this document from the portal — its uploader, a clinic
        administrator or a system administrator. Everybody else reads it
        only. The caller still checks the player / injury access."""
        self.ensure_one()
        user = user or self.env.user
        return bool(
            self.sudo().created_by_id == user
            or user.has_group('bemade_sports_clinic.group_sports_clinic_admin')
            or user.has_group('base.group_system'))

    def _sc_portal_archive(self, user=None):
        """Task 1432: archive from the portal (already permission-checked
        by the caller) and leave an internal note on the player that
        notifies nobody. Owner decision 2026-10-31: the note is BILINGUAL
        whatever the deleter's language (the player chatter is shared by
        French and English staff) — « Document « X » supprimé par Y /
        Document "X" deleted by Y » — so it is a fixed string, not a
        translated term; the names are escaped."""
        user = user or self.env.user
        for doc in self.sudo():
            doc.active = False
            doc.patient_id.message_post(
                body=Markup(
                    'Document « %(name)s » supprimé par %(user)s'
                    ' / Document "%(name)s" deleted by %(user)s'
                ) % {'name': doc.name or '', 'user': user.name or ''},
                message_type='comment',
                subtype_xmlid='mail.mt_note',
                author_id=user.partner_id.id,
            )
        return True
    
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
