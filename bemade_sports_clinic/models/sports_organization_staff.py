"""Task 1415 — organization-level staff, propagated to every team of the org.

The access model of this addon keys on REAL ``sports.team.staff`` rows (record
rules, controller guards, follower recompute, digests, portal-group grant).
Organization staff is therefore *materialized*: an organization line fans out
into one ``sports.team.staff`` row per team of the organization
(``source = 'org'``, ``org_staff_line_id`` = the line), reconciled by
``_sync()`` on every trigger and nightly as a safety net.

Precedence on a (team, partner) pair: a hand-made team row (``manual``) wins —
the line reports « already defined on the team » for that team and takes over
at the next sync once the manual row is gone; an event-coverage row
(``event``, task 539) is ADOPTED by the organization (source flipped to
``org``, its ``temporary_event_ids`` kept so #539's detach logic is unchanged).

Per-team exceptions live on the line: role *overrides* (one team, another role)
and *exclusions* (teams where the person must not appear). Head-role
collisions (a second head_coach / head_therapist on a team) fall back to
coach / therapist on that team and are reported « demoted ».

Side effects are batched: rows are created / written / unlinked under
``sports_staff_batch`` (the per-row hooks stay quiet) and the follower
recompute runs once per touched team, the portal-group update once per
touched user (``_apply_staff_side_effects``). Task 1416 stacks on these
helpers — keep them importable and argument-driven.
"""
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Same selection as sports.team.staff.role (kept in step by hand: the staff
# model, the mass-assign wizard and this model all spell it out).
STAFF_ROLES = [
    ("head_coach", "Head Coach"),
    ("head_therapist", "Head Therapist"),
    ("coach", "Coach"),
    ("therapist", "Therapist"),
    ("doctor", "Doctor"),
    ("other", "Other"),
]
# A second head on a team falls back to the plain role.
HEAD_FALLBACK = {"head_coach": "coach", "head_therapist": "therapist"}

TEAM_STATES = [
    ("synced", "Synced"),
    ("demoted", "Demoted (team already has a head)"),
    ("manual", "Already defined on the team"),
    ("excluded", "Excluded"),
    ("ineligible", "Contact archived / no active user"),
]

# Context flags understood by the reconciler and the staff hooks.
CTX_SYNC = {
    "org_staff_sync": True,  # bypass the org-locked guard on sports.team.staff
    "sports_staff_batch": True,  # per-row side effects deferred to the batch
    "active_test": False,
}


class SportsOrganizationStaff(models.Model):
    _name = "sports.organization.staff"
    _description = "Organization Staff"
    _inherit = ["mail.thread"]
    _order = "organization_id, sequence, id"

    sequence = fields.Integer(default=10)
    organization_id = fields.Many2one(
        comodel_name="res.partner",
        string="Organization",
        required=True,
        index=True,
        ondelete="cascade",
        domain=[("is_company", "=", True)],
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Staff Member",
        required=True,
        index=True,
        ondelete="cascade",
        domain=[("is_company", "=", False)],
        tracking=True,
    )
    role = fields.Selection(
        selection=STAFF_ROLES,
        required=True,
        default="therapist",
        tracking=True,
        help="Role applied on every team of the organization, unless a "
             "per-team override says otherwise.",
    )
    silent_notifications = fields.Boolean(
        string="No Notifications",
        tracking=True,
        help="Granted access on every team but not added as a follower of "
             "the teams' patients/injuries.",
    )
    active = fields.Boolean(default=True, tracking=True)
    note = fields.Text()
    override_ids = fields.One2many(
        comodel_name="sports.organization.staff.override",
        inverse_name="line_id",
        string="Role Overrides",
        help="Teams where this person holds a different role.",
    )
    excluded_team_ids = fields.Many2many(
        comodel_name="sports.team",
        relation="sports_org_staff_excluded_team_rel",
        column1="line_id",
        column2="team_id",
        string="Excluded Teams",
        domain="[('parent_id', '=', organization_id)]",
        help="Teams of the organization where this person must NOT appear.",
    )
    team_staff_ids = fields.One2many(
        comodel_name="sports.team.staff",
        inverse_name="org_staff_line_id",
        string="Propagated Team Staff",
        readonly=True,
    )
    team_state_ids = fields.One2many(
        comodel_name="sports.organization.staff.team",
        inverse_name="line_id",
        string="Team Status",
        readonly=True,
    )
    team_count = fields.Integer(compute="_compute_counts", string="Teams")
    synced_count = fields.Integer(compute="_compute_counts", string="Propagated")
    manual_count = fields.Integer(compute="_compute_counts", string="Already on team")

    _org_partner_unique = models.Constraint(
        "unique(organization_id, partner_id)",
        "This person is already on the organization's staff list.",
    )

    @api.depends("team_state_ids.state")
    def _compute_counts(self):
        for line in self:
            states = line.team_state_ids
            line.team_count = len(states)
            line.synced_count = len(
                states.filtered(lambda s: s.state in ("synced", "demoted"))
            )
            line.manual_count = len(states.filtered(lambda s: s.state == "manual"))

    @api.depends("partner_id", "organization_id", "role")
    def _compute_display_name(self):
        roles = dict(self._fields["role"]._description_selection(self.env))
        for line in self:
            line.display_name = "%s (%s) @ %s" % (
                line.partner_id.display_name or "",
                roles.get(line.role, line.role or ""),
                line.organization_id.display_name or "",
            )

    @api.constrains("excluded_team_ids", "organization_id")
    def _check_excluded_in_org(self):
        for line in self:
            bad = line.excluded_team_ids.filtered(
                lambda t: t.parent_id != line.organization_id
            )
            if bad:
                raise ValidationError(
                    _("Excluded teams must belong to the organization: %s")
                    % ", ".join(bad.mapped("display_name"))
                )

    @api.constrains("partner_id")
    def _check_partner_person(self):
        for line in self:
            if line.partner_id.is_company:
                raise ValidationError(
                    _("An organization staff member must be a person, not a company.")
                )

    # ------------------------------------------------------------------
    # triggers
    # ------------------------------------------------------------------
    _SYNC_FIELDS = (
        "partner_id",
        "organization_id",
        "role",
        "silent_notifications",
        "active",
        "override_ids",
        "excluded_team_ids",
    )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get("org_staff_skip_sync"):
            lines._sync()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if set(vals) & set(self._SYNC_FIELDS) and not self.env.context.get(
            "org_staff_skip_sync"
        ):
            self._sync()
        return res

    def unlink(self):
        # Drop the propagated rows through the ORM (followers, activities,
        # portal groups) before the line goes — ``ondelete='set null'`` alone
        # would leave orphan org rows behind until the nightly cleanup.
        rows = self.with_context(active_test=False).team_staff_ids
        touched = self._unlink_staff_rows(rows)
        self.with_context(active_test=False).team_state_ids.unlink()
        res = super().unlink()
        self._apply_staff_side_effects(**touched)
        return res

    # ------------------------------------------------------------------
    # reconciler
    # ------------------------------------------------------------------
    def _partner_eligible(self):
        """Never propagate for an archived contact or a contact whose user
        accounts are all archived (same semantics as
        ``sports.team.staff._is_follower_eligible`` / the archive purge):
        the purge deleted their rows on purpose and the reconcile must not
        resurrect them."""
        self.ensure_one()
        partner = self.partner_id.sudo().with_context(active_test=False)
        if not partner.active:
            return False
        users = partner.user_ids
        if users and not users.filtered("active"):
            return False
        return True

    @api.model
    def _staff_env(self):
        return self.env["sports.team.staff"].sudo().with_context(**CTX_SYNC)

    @api.model
    def _effective_role(self, team, partner, role, existing_row=None):
        """The role a row on ``team`` may take: ``role`` unless it is a head
        role already held by ANOTHER row of the team, in which case the plain
        fallback. Returns (role, demoted)."""
        if role not in HEAD_FALLBACK:
            return role, False
        Staff = self._staff_env()
        domain = [("team_id", "=", team.id), ("role", "=", role)]
        if existing_row:
            domain.append(("id", "!=", existing_row.id))
        else:
            domain.append(("partner_id", "!=", partner.id))
        if Staff.search_count(domain):
            return HEAD_FALLBACK[role], True
        return role, False

    def _sync(self, teams=None):
        """Reconcile the propagated ``sports.team.staff`` rows of these lines.

        ``teams``: restrict the pass to these teams (a team created under /
        re-parented into or out of the organization); default = every team of
        each line's organization plus any team the line still owns a row on.
        Idempotent; safe to run nightly. Runs sudo.
        """
        Staff = self._staff_env()
        State = self.env["sports.organization.staff.team"].sudo()
        touched_teams = self.env["sports.team"].sudo()
        touched_users = self.env["res.users"].sudo()
        unlinked_teams = self.env["sports.team"].sudo()
        created = Staff.browse()

        for line in self.sudo().with_context(active_test=False):
            org = line.organization_id
            org_teams = org.with_context(active_test=False).owned_team_ids
            owned = line.team_staff_ids  # active_test off via context
            if teams is not None:
                org_teams = org_teams & teams
                owned = owned.filtered(lambda r: r.team_id in teams)
            eligible = line.active and line._partner_eligible()
            partner = line.partner_id
            overrides = {o.team_id.id: o.role for o in line.override_ids}
            excluded = line.excluded_team_ids

            existing = Staff.search(
                [("partner_id", "=", partner.id), ("team_id", "in", org_teams.ids)]
            )
            by_team = {r.team_id.id: r for r in existing}
            desired_rows = Staff.browse()
            states = {}

            for team in org_teams:
                row = by_team.get(team.id)
                if not eligible:
                    states[team.id] = ("ineligible", False)
                    continue
                if team in excluded:
                    states[team.id] = ("excluded", False)
                    continue
                wanted = overrides.get(team.id, line.role)
                if row and row.source == "manual":
                    states[team.id] = ("manual", row.role)
                    continue
                if row:
                    # org (ours or a stale line's) or event → adopt / update.
                    role, demoted = self._effective_role(team, partner, wanted, row)
                    vals = {}
                    if row.role != role:
                        vals["role"] = role
                    if row.silent_notifications != line.silent_notifications:
                        vals["silent_notifications"] = line.silent_notifications
                    if row.source != "org":
                        vals["source"] = "org"
                    if row.org_staff_line_id != line:
                        vals["org_staff_line_id"] = line.id
                    if vals:
                        row.write(vals)
                        touched_teams |= team
                        touched_users |= row.user_ids
                    desired_rows |= row
                else:
                    role, demoted = self._effective_role(team, partner, wanted)
                    row = Staff.create(
                        {
                            "team_id": team.id,
                            "partner_id": partner.id,
                            "role": role,
                            "silent_notifications": line.silent_notifications,
                            "source": "org",
                            "org_staff_line_id": line.id,
                        }
                    )
                    created |= row
                    desired_rows |= row
                    touched_teams |= team
                    touched_users |= row.user_ids
                states[team.id] = ("demoted" if demoted else "synced", role)

            stale = owned - desired_rows
            if stale:
                t = self._unlink_staff_rows(stale)
                touched_teams |= t["teams"]
                touched_users |= t["users"]
                unlinked_teams |= t["teams"]

            # Per-team status rows (upsert; teams gone from the org drop out).
            current = {s.team_id.id: s for s in line.team_state_ids}
            gone = line.team_state_ids.filtered(lambda s: s.team_id.id not in states)
            if teams is not None:
                gone = gone.filtered(lambda s: s.team_id in teams)
            if gone:
                gone.unlink()
            for team in org_teams:
                state, role = states.get(team.id, ("synced", False))
                rec = current.get(team.id)
                vals = {"state": state, "role": role or False}
                if rec:
                    if rec.state != state or rec.role != (role or False):
                        rec.write(vals)
                else:
                    State.create(dict(vals, line_id=line.id, team_id=team.id))

        self._apply_staff_side_effects(
            teams=touched_teams, users=touched_users, unlinked_teams=unlinked_teams
        )
        return created

    @api.model
    def _unlink_staff_rows(self, rows):
        """Unlink propagated rows in batch mode; returns the teams / users the
        caller must run the side effects for."""
        rows = rows.sudo().with_context(**CTX_SYNC).exists()
        result = {
            "teams": rows.mapped("team_id"),
            "users": rows.mapped("user_ids"),
            "unlinked_teams": rows.mapped("team_id"),
        }
        # An adopted event-coverage row whose event is still open goes back to
        # the event (#539: source event, therapist, silent) instead of vanishing
        # with the organization line — the TP keeps the coverage access
        # (review finding).
        handed_back = rows.browse()
        for row in rows:
            if row.is_auto_created and row.temporary_event_ids.filtered(
                lambda e: e._is_active_for_access()
            ):
                row.write(self._event_hand_back_vals())
                handed_back |= row
        rows -= handed_back
        result["unlinked_teams"] = rows.mapped("team_id")
        if rows:
            rows.unlink()
        return result

    @api.model
    def _event_hand_back_vals(self):
        """Values that turn a row back into a plain #539 event-coverage row."""
        return {
            "source": "event",
            "org_staff_line_id": False,
            "role": "therapist",
            "silent_notifications": True,
        }

    @api.model
    def _apply_staff_side_effects(self, teams=None, users=None, unlinked_teams=None):
        """Run ONCE what the per-row sports.team.staff hooks skipped in batch
        mode: follower recompute per touched team's patients, stale-activity
        cleanup for the teams rows were removed from, portal-group update per
        touched user."""
        Staff = self.env["sports.team.staff"].sudo()
        teams = (teams or self.env["sports.team"]).sudo().exists()
        unlinked_teams = (unlinked_teams or self.env["sports.team"]).sudo().exists()
        if teams:
            patients = teams.with_context(active_test=False).mapped("patient_ids")
            if patients:
                patients.sudo().recompute_followers()
        if unlinked_teams:
            patients = unlinked_teams.with_context(active_test=False).mapped(
                "patient_ids"
            )
            if patients:
                patients.injury_ids.sudo()._cleanup_stale_mail_activities()
        users = (users or self.env["res.users"]).sudo().with_context(
            active_test=False
        ).exists()
        for user in users:
            Staff._update_all_portal_groups(user)

    # ------------------------------------------------------------------
    # entry points
    # ------------------------------------------------------------------
    @api.model
    def _sync_for_partners(self, partners):
        """Re-evaluate every organization line of these people (archive /
        unarchive of the contact or of a user account)."""
        lines = self.sudo().with_context(active_test=False).search(
            [("partner_id", "in", partners.ids)]
        )
        if lines:
            lines._sync()
        return lines

    @api.model
    def _cleanup_orphan_org_rows(self):
        """Organization-sourced staff rows that no line owns any more (line
        deleted behind the ORM, line archived, team moved out of the org) are
        removed. Part of the nightly reconcile."""
        Staff = self._staff_env()
        orphans = Staff.search(
            [
                ("source", "=", "org"),
                "|",
                ("org_staff_line_id", "=", False),
                ("org_staff_line_id.active", "=", False),
            ]
        )
        orphans |= Staff.search(
            [("source", "=", "org"), ("org_staff_line_id", "!=", False)]
        ).filtered(
            lambda r: r.team_id.parent_id != r.org_staff_line_id.organization_id
            or r.partner_id != r.org_staff_line_id.partner_id
        )
        touched = self._unlink_staff_rows(orphans)
        self._apply_staff_side_effects(**touched)
        return orphans

    @api.model
    def _cron_sync_organization_staff(self):
        """Nightly safety net: drop orphan org rows, then reconcile every
        line (archived lines included — their rows must be gone)."""
        self._cleanup_orphan_org_rows()
        lines = self.sudo().with_context(active_test=False).search([])
        if lines:
            lines._sync()
        return True

    def action_sync_now(self):
        self._sync()
        return True

    def action_open_team_staff(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Propagated Team Staff"),
            "res_model": "sports.team.staff",
            "view_mode": "list,form",
            "domain": [("org_staff_line_id", "=", self.id)],
            "context": {"create": False},
        }


class SportsOrganizationStaffOverride(models.Model):
    _name = "sports.organization.staff.override"
    _description = "Organization Staff — Role Override"
    _order = "line_id, team_id"

    line_id = fields.Many2one(
        comodel_name="sports.organization.staff",
        required=True,
        ondelete="cascade",
        index=True,
    )
    organization_id = fields.Many2one(
        related="line_id.organization_id", store=False
    )
    team_id = fields.Many2one(
        comodel_name="sports.team",
        required=True,
        ondelete="cascade",
        domain="[('parent_id', '=', organization_id)]",
    )
    role = fields.Selection(selection=STAFF_ROLES, required=True)

    _override_team_unique = models.Constraint(
        "unique(line_id, team_id)",
        "Only one role override per team.",
    )

    @api.constrains("team_id", "line_id")
    def _check_team_in_org(self):
        for rec in self:
            if rec.team_id.parent_id != rec.line_id.organization_id:
                raise ValidationError(
                    _("Override team %s does not belong to the organization.")
                    % rec.team_id.display_name
                )

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("org_staff_skip_sync"):
            recs.line_id._sync()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("org_staff_skip_sync"):
            self.line_id._sync()
        return res

    def unlink(self):
        lines = self.line_id
        res = super().unlink()
        if not self.env.context.get("org_staff_skip_sync"):
            lines.exists()._sync()
        return res


class SportsOrganizationStaffTeam(models.Model):
    """One row per (line × team of the organization): what the reconciler
    decided for that team. Maintained by ``_sync`` only; read-only in the UI.
    """

    _name = "sports.organization.staff.team"
    _description = "Organization Staff — Team Status"
    _order = "line_id, team_id"

    line_id = fields.Many2one(
        comodel_name="sports.organization.staff",
        required=True,
        ondelete="cascade",
        index=True,
    )
    team_id = fields.Many2one(
        comodel_name="sports.team", required=True, ondelete="cascade"
    )
    state = fields.Selection(selection=TEAM_STATES, required=True, default="synced")
    role = fields.Selection(
        selection=STAFF_ROLES,
        string="Effective Role",
        help="The role actually held on the team (a head role falls back to "
             "the plain role when the team already has a head).",
    )

    _line_team_unique = models.Constraint(
        "unique(line_id, team_id)",
        "One status per team.",
    )
