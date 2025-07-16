from odoo import models, fields, api, _, Command


class User(models.Model):
    _inherit = "res.users"

    accessible_team_ids = fields.Many2many(
        comodel_name="sports.team",
        compute="_compute_accessible_team_ids",
        inverse="_inverse_accessible_team_ids",
    )

    def _compute_accessible_team_ids(self):
        for rec in self:
            rec.accessible_team_ids = rec.partner_id.teams_served_ids

    def _inverse_accessible_team_ids(self):
        for rec in self:
            removed_teams = rec.partner_id.teams_served_ids - rec.accessible_team_ids
            added_teams = rec.accessible_team_ids - rec.partner_id.teams_served_ids
            removed_teams = rec.partner_id.teams_served_ids.filtered(
                lambda team: team in removed_teams
            )
            removed_teams.remove_access(self)
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
