from odoo import models, fields, api, _, Command


class User(models.Model):
    _inherit = "res.users"

    is_treatment_professional = fields.Boolean(
        compute="_compute_is_treatment_professional", store=True
    )

    accessible_team_ids = fields.Many2many(
        comodel_name="sports.team",
        compute="_compute_accessible_team_ids",
        inverse="_inverse_accessible_team_ids",
    )

    @api.depends("groups_id")
    def _compute_is_treatment_professional(self):
        for rec in self:
            rec.is_treatment_professional = rec.has_group(
                "bemade_sports_clinic.group_sports_clinic_treatment_professional"
            )

    def _compute_accessible_team_ids(self):
        for rec in self:
            rec.accessible_team_ids = rec.partner_id.teams_served_ids

    def _inverse_accessible_team_ids(self):
        for rec in self:
            removed_teams = (
                rec.partner_id.staff_ids.mapped("team_id") - rec.accessible_team_ids
            )
            added_teams = rec.accessible_team_ids - rec.partner_id.staff_ids.mapped(
                "team_id"
            )
            rec.partner_id.staff_ids.filtered(
                lambda team: team in removed_teams
            ).unlink()
            self.env["sports.team.staff"].create(
                [
                    {
                        "team_id": team.id,
                        "partner_id": rec.partner_id.id,
                        "role": "other",
                    }
                    for team in added_teams
                ]
            )
