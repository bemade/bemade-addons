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
    # Task 1415: organization-level staff (company partner = sports.team
    # parent), propagated to every team of the organization.
    org_staff_ids = fields.One2many(
        comodel_name="sports.organization.staff",
        inverse_name="organization_id",
        string="Organization Staff",
    )
    org_staff_line_ids = fields.One2many(
        comodel_name="sports.organization.staff",
        inverse_name="partner_id",
        string="Organization Staff Lines",
        help="The organizations this person serves as organization-level staff.",
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
        if "active" in vals:
            # Task 1415: organization lines re-evaluate eligibility (archived
            # contact -> rows gone / status « ineligible »; unarchived -> the
            # line, still the declared intent, propagates again).
            self.env["sports.organization.staff"]._sync_for_partners(self)
        return res

    def _sports_clinic_purge_archived_staff(self):
        """When a staff contact (or their user) loses access through
        archiving, scrub the lingering side effects (task 399):

        - drop the person from future events' assigned staff and unlink any
          auto-created event-coverage staff records,
        - DELETE their team-membership (sports.team.staff) rows — archiving
          used to only soft-hide them via the related partner ``active``
          flag, so unarchiving the user silently restored their old team
          access; a returning staff member must instead be explicitly
          re-added to whatever team they now serve (dev-review 2026-07-04).
          Rows are kept only while the partner still has another active
          user account.
        - recompute followers on every affected team's patients so the
          archived person stops being a follower of patients/injuries, and
          clean up stale treatment-professional assignments / mail
          activities on the affected injuries.

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
        self._sports_clinic_purge_future_events()
        # The future-event purge may already have unlinked orphaned
        # auto-created coverage rows via the event sync — drop them from the
        # set before touching their fields.
        staff = staff.exists()
        revoked = self.filtered(
            lambda p: not p.active
            or not p.sudo().with_context(active_test=False).user_ids.filtered("active")
        )
        doomed = staff.filtered(lambda s: s.partner_id in revoked)
        if doomed:
            # The staff unlink hook recomputes followers, cleans injury
            # activities and reconciles portal groups. org_staff_sync: the
            # purge may delete organization-sourced rows too (task 1415) —
            # the reconciler never resurrects a revoked person.
            doomed.with_context(org_staff_sync=True).unlink()
        if patients:
            patients.sudo().recompute_followers()
            patients.injury_ids.sudo()._cleanup_stale_mail_activities()

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

    # Core identity PII wiped on Law 25 anonymization. Only fields that exist on
    # the installed res.partner are written (e.g. ``mobile`` is not in Odoo 19
    # core), so the set stays valid across localizations.
    _LAW25_PII_FIELDS = (
        "name",
        "email",
        "phone",
        "mobile",
        "street",
        "street2",
        "city",
        "zip",
        "vat",
        "function",
        "comment",
        "image_1920",
    )

    def _law25_anonymize(self):
        """Irreversibly overwrite core identity PII on the partner in place.

        The partner record itself is preserved (``ondelete='restrict'`` from
        sports.patient, and it is referenced by invoices/appointments that a
        statute may require kept — Law 25's carve-out). Only the identity
        *values* are scrubbed. Tracking is suppressed so the wipe does not log
        the old values; residual chatter is purged separately by the caller.
        """
        for partner in self:
            partner = partner.sudo()
            vals = {}
            for fname in self._LAW25_PII_FIELDS:
                if fname not in partner._fields:
                    continue
                vals[fname] = (
                    _("Anonymized Contact %s") % partner.id
                    if fname == "name"
                    else False
                )
            partner.with_context(
                patient_update=True,
                tracking_disable=True,
                mail_create_nolog=True,
            ).write(vals)

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
