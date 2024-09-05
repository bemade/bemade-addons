from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError


class Partner(models.Model):
    _inherit = "res.partner"

    owned_team_ids = fields.One2many(
        comodel_name="sports.team", inverse_name="parent_id"
    )
    staff_ids = fields.One2many(
        comodel_name="sports.team.staff", inverse_name="team_id"
    )
    team_staff_rel_ids = fields.One2many(
        comodel_name="sports.team.staff",
        inverse_name="partner_id",
        string="Employer(s)",
        help="The teams this person works for.",
    )
    teams_served_ids = fields.One2many(
        comodel_name="sports.team",
        compute="_compute_teams_served",
        inverse="_inverse_teams_served",
    )
    patient_ids = fields.One2many(
        comodel_name="sports.patient", inverse_name="partner_id"
    )

    def write(self, vals):
        if self.patient_ids and "name" in vals:
            raise ValidationError(
                _("To change a patient's name, change it from the patient form.")
            )
        return super().write(vals)

    @api.depends("team_staff_rel_ids.team_id")
    def _compute_teams_served(self):
        for rec in self:
            rec.teams_served_ids = rec.team_staff_rel_ids.mapped("team_id")

    @api.depends("team_staff_rel_ids.team_id")
    def _inverse_teams_served(self):
        for rec in self:
            for staff in rec.team_staff_rel_ids:
                if staff.team_id not in rec.teams_served_ids:
                    staff.unlink()
            served_teams = rec.team_staff_rel_ids.mapped("team_id")
            for team in rec.teams_served_ids:
                if team not in served_teams:
                    raise UserError(
                        "To add a staff member to a team, use the team view."
                    )
