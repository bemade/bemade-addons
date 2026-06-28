from odoo import models, fields, api, _, Command
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
    
    # Boolean field to identify venues
    is_venue = fields.Boolean(
        string='Is Venue',
        default=False,
        help='Check this box if this contact represents a venue/location'
    )

    def write(self, vals):
        if (
            self.patient_ids
            and "name" in vals
            and not self.env.context.get("patient_update")
        ):
            raise ValidationError(
                _("To change a patient's name, change it from the patient form.")
            )
        res = super().write(vals)
        if "active" in vals and not vals.get("active"):
            self._sports_clinic_purge_archived_staff()
        return res

    def _sports_clinic_purge_archived_staff(self):
        """When a staff contact (or their user) loses access through
        archiving, scrub the lingering side effects (task 399):

        - recompute followers on every affected team's patients so the
          archived person stops being a follower of patients/injuries,
        - drop the person from future events' assigned staff and unlink any
          auto-created event-coverage staff records,
        - clean up stale treatment-professional assignments / mail activities
          on the affected injuries.

        Keyed off the staff/user state rather than partner state alone, so a
        contact that legitimately stays active while its user is revoked is
        still purged.
        """
        Staff = self.env["sports.team.staff"].sudo().with_context(
            active_test=False
        )
        staff = Staff.search([("partner_id", "in", self.ids)])
        if not staff:
            return
        patients = staff.mapped("team_id.patient_ids")
        if patients:
            patients.sudo().recompute_followers()
            patients.injury_ids.sudo()._cleanup_stale_treatment_professionals()
            patients.injury_ids.sudo()._cleanup_stale_mail_activities()
        self._sports_clinic_purge_future_events()

    def _sports_clinic_purge_future_events(self):
        """Remove the archived partners' users from any not-yet-past event's
        assigned staff. Writing assigned_staff_ids triggers the event's
        auto-staff sync, which unlinks orphaned auto-created staff records."""
        users = self.with_context(active_test=False).user_ids
        if not users:
            return
        now = fields.Datetime.now()
        events = self.env["sports.event"].sudo().with_context(
            active_test=False
        ).search([
            ("date_end", ">=", now),
            ("assigned_staff_ids", "in", users.ids),
        ])
        events = events.filtered(lambda e: e._is_active_for_access())
        for event in events:
            event.write({
                "assigned_staff_ids": [Command.unlink(u.id) for u in users],
            })

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
                        _("To add a staff member to a team, use the team view.")
                    )
