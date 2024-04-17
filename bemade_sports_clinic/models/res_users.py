from odoo import models, fields, api, _


class User(models.Model):
    _inherit = 'res.users'

    is_treatment_professional = fields.Boolean(
        compute="_compute_is_treatment_professional", store=True)

    accessible_team_ids = fields.Many2many(
        comodel_name="sports.team",
        relation="sports_team_res_users_rel",
        column1="user_id",
        column2="team_id",
        string="Accessible Sports Teams",
    )

    @api.depends('groups_id')
    def _compute_is_treatment_professional(self):
        for rec in self:
            rec.is_treatment_professional = rec.has_group(
                'bemade_sports_clinic.group_sports_clinic_treatment_professional')
