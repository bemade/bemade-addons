from odoo import models, fields, api
from odoo.addons.phone_validation.tools import phone_validation
from .sc_phone import sc_phone_is_valid


class PatientContact(models.Model):
    _name = 'sports.patient.contact'
    _description = "Emergency or other contacts for a patient."
    # Task 1645: the mobile is normalized / refused in create / write.
    _inherit = ["sc.phone.mixin"]
    _sc_phone_fields = ("mobile",)
    
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
    sc_phone_invalid = fields.Boolean(
        string="Phone number to fix", compute="_compute_sc_phone_invalid", store=True)

    @api.depends('mobile', 'patient_id.country_id')
    def _compute_sc_phone_invalid(self):
        for contact in self:
            contact.sc_phone_invalid = not sc_phone_is_valid(
                contact.env, contact.mobile, contact._sc_phone_country())

    def _sc_phone_country(self, vals=None):
        patient = self.env['sports.patient']
        if vals and vals.get('patient_id'):
            patient = patient.browse(vals['patient_id'])
        patient = patient or self[:1].patient_id
        return patient.country_id or self.env.company.country_id

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
