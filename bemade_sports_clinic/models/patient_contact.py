from odoo import models, fields, api
from odoo.addons.phone_validation.tools import phone_validation
from .sc_patient_owner_guard import sc_check_patient_unchanged


class PatientContact(models.Model):
    _name = 'sports.patient.contact'
    _description = "Emergency or other contacts for a patient."
    
    @api.model
    def _valid_field_parameter(self, field, name):
        # Allow 'unaccent' parameter for fields
        return name == 'unaccent' or super()._valid_field_parameter(field, name)
    
    sequence = fields.Integer(required=True, default=0)
    name = fields.Char(unaccent=True)
    contact_type = fields.Selection(selection=[
        ('mother', 'Mother'),
        ('father', 'Father'),
        ('other', 'Other'),
    ], required=True)
    mobile = fields.Char(unaccent=False)
    email = fields.Char(string='Email')
    patient_id = fields.Many2one(comodel_name='sports.patient', string='Patient')

    def write(self, vals):
        # Adversarial review 2026-10-22: never moved onto another player.
        sc_check_patient_unchanged(self, vals)
        return super().write(vals)

    @api.onchange('mobile')
    def _onchange_mobile_validation(self):
        if self.mobile:
            self.mobile = self._phone_format(self.mobile, force_format="INTERNATIONAL")

    def _phone_format(self, number, force_format='E164'):
        country = self.patient_id.country_id or self.env.company.country_id
        if not country or not number:
            return number
        return phone_validation.phone_format(
            number,
            country.code if country else None,
            country.phone_code if country else None,
            force_format=force_format,
            raise_exception=False
        )
