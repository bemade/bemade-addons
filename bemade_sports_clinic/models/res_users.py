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

    @api.depends("groups_id", "partner_id", "partner_id.staff_ids", "partner_id.staff_ids.role")
    def _compute_is_treatment_professional(self):
        for rec in self:
            # Check if user has the security group
            has_security_group = rec.has_group(
                "bemade_sports_clinic.group_sports_clinic_treatment_professional"
            )
            
            # Check if user is linked to any team staff as head therapist or therapist
            is_therapist_staff = False
            if rec.partner_id:
                staff_records = self.env['sports.team.staff'].sudo().search([
                    ('partner_id', '=', rec.partner_id.id),
                    ('role', 'in', ['head_therapist', 'therapist'])
                ])
                is_therapist_staff = bool(staff_records)
            
            # Set field based on either condition
            rec.is_treatment_professional = has_security_group or is_therapist_staff

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
