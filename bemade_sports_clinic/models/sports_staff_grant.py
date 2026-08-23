"""Task 1416 — temporary (dated) staff access: replacement therapists.

The access model of this addon keys on REAL ``sports.team.staff`` rows (record
rules, controller guards, followers, digests, portal-group grant) and the
record rules cannot express a per-row date window (a ``team -> staff -> user``
traversal on ~29 leaves). Temporary access is therefore *materialized inside
its window only*: a ``sports.staff.grant`` (person, role, dates, team OR
organization scope) is the declared intent; the reconciler creates one
``sports.team.staff`` row ``source = 'temp'`` (``grant_id`` = the grant) per
team in scope while ``date_start <= now < date_end`` and removes it after.
Nothing in ``security/`` changes.

Precedence on a (team, partner) pair: manual > org > temp > event. A hand-made
or organization-sourced row means the grant is « already covered » on that
team (no temp row); an event-coverage row (task 539) is ADOPTED by the grant
(source flipped to ``temp``; its ``temporary_event_ids`` kept) and handed back
to the event sync when the grant ends while the event is still open.

Head roles are never granted temporarily (therapist / coach / other only).

Side effects are batched through #1415's helpers: rows are created / written /
unlinked under ``sports_staff_batch`` and the follower recompute runs once per
touched team, the portal-group update once per touched user
(``sports.organization.staff._apply_staff_side_effects``).

Lifecycle: ``state`` scheduled -> active -> expired (or revoked), maintained by
``_reconcile()`` — run on create / write, by « Revoke now » and hourly by
``sports.team.staff._reconcile_timed_rows()`` (the ONE timed-access job, shared
with the #539 event coverage rows).
"""
import logging

from markupsafe import Markup, escape

from odoo import api, fields, models, _, Command
from odoo.exceptions import ValidationError, UserError
from odoo.tools.misc import format_datetime

_logger = logging.getLogger(__name__)

# Roles a grant may hand out: never a head role (a replacement must not take
# over the team's head_coach / head_therapist slot).
TEMP_ROLES = [
    ("therapist", "Therapist"),
    ("coach", "Coach"),
    ("other", "Other"),
]

GRANT_STATES = [
    ("scheduled", "Scheduled"),
    ("active", "Active"),
    ("expired", "Ended"),
    ("revoked", "Revoked"),
]


class SportsStaffGrant(models.Model):
    _name = "sports.staff.grant"
    _description = "Temporary Staff Access"
    _inherit = ["mail.thread"]
    _order = "date_start desc, id desc"

    scope = fields.Selection(
        selection=[("team", "Team"), ("organization", "Organization")],
        required=True,
        default="team",
        tracking=True,
        help="Team: access to one team. Organization: access to every team "
             "of the organization (teams created under it during the window "
             "are picked up by the hourly reconcile).",
    )
    team_id = fields.Many2one(
        comodel_name="sports.team",
        string="Team",
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    organization_id = fields.Many2one(
        comodel_name="res.partner",
        string="Organization",
        ondelete="cascade",
        index=True,
        tracking=True,
        domain=[("is_company", "=", True)],
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Staff Member",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
        domain=[("is_company", "=", False)],
    )
    role = fields.Selection(
        selection=TEMP_ROLES,
        required=True,
        default="therapist",
        tracking=True,
        help="Role held on the team(s) during the window. Head roles are "
             "never granted temporarily.",
    )
    silent_notifications = fields.Boolean(
        string="No Notifications",
        tracking=True,
        help="Granted access but not added as a follower of the teams' "
             "patients/injuries during the window.",
    )
    date_start = fields.Datetime(
        string="Start",
        required=True,
        tracking=True,
        default=fields.Datetime.now,
        help="The access opens at this moment (hourly reconcile, or "
             "immediately when the grant is saved with a start in the past).",
    )
    date_end = fields.Datetime(
        string="End",
        required=True,
        tracking=True,
        help="The access is removed after this moment (hourly reconcile).",
    )
    state = fields.Selection(
        selection=GRANT_STATES,
        required=True,
        default="scheduled",
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
        help="Scheduled: the window has not opened yet. Active: the temporary "
             "staff rows exist. Expired: the window ended, rows removed. "
             "Revoked: ended by hand before the end date.",
    )
    note = fields.Text(help="Internal note (no patient information).")
    revoked_by_id = fields.Many2one(
        comodel_name="res.users", string="Revoked By", readonly=True, copy=False
    )
    revoked_on = fields.Datetime(string="Revoked On", readonly=True, copy=False)
    staff_ids = fields.One2many(
        comodel_name="sports.team.staff",
        inverse_name="grant_id",
        string="Temporary Staff Rows",
        readonly=True,
    )
    staff_count = fields.Integer(compute="_compute_team_coverage", string="Rows")
    scope_team_ids = fields.Many2many(
        comodel_name="sports.team",
        compute="_compute_team_coverage",
        string="Teams in Scope",
    )
    covered_team_ids = fields.Many2many(
        comodel_name="sports.team",
        compute="_compute_team_coverage",
        string="Already Covered",
        help="Teams in scope where this person already has a manual or "
             "organization staff row (or another temporary access): no "
             "temporary row is created there.",
    )
    partner_eligible = fields.Boolean(
        compute="_compute_team_coverage",
        string="Eligible",
        help="False when the contact is archived or all their user accounts "
             "are archived: nothing is materialized.",
    )

    # ------------------------------------------------------------------
    # display / constraints
    # ------------------------------------------------------------------
    @api.depends("partner_id", "role", "scope", "team_id", "organization_id")
    def _compute_display_name(self):
        roles = dict(self._fields["role"]._description_selection(self.env))
        for grant in self:
            target = grant.team_id if grant.scope == "team" else grant.organization_id
            grant.display_name = "%s (%s) @ %s" % (
                grant.partner_id.display_name or "",
                roles.get(grant.role, grant.role or ""),
                target.display_name or "",
            )

    @api.depends(
        "scope", "team_id", "organization_id", "partner_id", "staff_ids",
        "partner_id.active", "partner_id.user_ids.active",
    )
    def _compute_team_coverage(self):
        Staff = self.env["sports.team.staff"].sudo().with_context(active_test=False)
        for grant in self:
            teams = grant._scope_teams()
            grant.scope_team_ids = teams
            grant.staff_count = len(grant.staff_ids)
            covered = self.env["sports.team"]
            if teams and grant.partner_id:
                others = Staff.search([
                    ("partner_id", "=", grant.partner_id.id),
                    ("team_id", "in", teams.ids),
                    "|",
                    ("source", "in", ("manual", "org")),
                    "&", ("source", "=", "temp"), ("grant_id", "!=", grant.id),
                ])
                covered = others.mapped("team_id")
            grant.covered_team_ids = covered
            grant.partner_eligible = bool(grant.partner_id) and grant._partner_eligible()

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for grant in self:
            if grant.date_start and grant.date_end and grant.date_end <= grant.date_start:
                raise ValidationError(_("The end of a temporary access must be after its start."))

    @api.constrains("scope", "team_id", "organization_id")
    def _check_scope_target(self):
        for grant in self:
            if grant.scope == "team" and not grant.team_id:
                raise ValidationError(_("A team-scoped temporary access needs a team."))
            if grant.scope == "organization" and not grant.organization_id:
                raise ValidationError(_("An organization-scoped temporary access needs an organization."))

    @api.constrains("role")
    def _check_role_not_head(self):
        allowed = {k for k, _label in TEMP_ROLES}
        for grant in self:
            if grant.role not in allowed:
                raise ValidationError(
                    _("Head roles are never granted temporarily (therapist, coach or other only).")
                )

    @api.constrains("partner_id")
    def _check_partner_person(self):
        for grant in self:
            if grant.partner_id.is_company:
                raise ValidationError(
                    _("A temporary access is granted to a person, not a company.")
                )

    # ------------------------------------------------------------------
    # hooks
    # ------------------------------------------------------------------
    _RECONCILE_FIELDS = (
        "scope", "team_id", "organization_id", "partner_id", "role",
        "silent_notifications", "date_start", "date_end", "state",
    )

    @api.model
    def _normalize_scope_vals(self, vals, current=None):
        scope = vals.get("scope") or (current and current.scope) or "team"
        if scope == "team":
            vals["organization_id"] = False
        else:
            vals["team_id"] = False
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "scope" in vals or "team_id" in vals or "organization_id" in vals:
                self._normalize_scope_vals(vals)
        grants = super().create(vals_list)
        if not self.env.context.get("staff_grant_skip_reconcile"):
            grants._reconcile()
        return grants

    def write(self, vals):
        if "scope" in vals:
            vals = dict(vals)
            self._normalize_scope_vals(vals)
        res = super().write(vals)
        if set(vals) & set(self._RECONCILE_FIELDS) and not self.env.context.get(
            "staff_grant_reconcile"
        ):
            self._reconcile()
        return res

    def unlink(self):
        rows = self.sudo().with_context(active_test=False).staff_ids
        foreign = rows.filtered(lambda r: r.source != "temp")
        if foreign:
            foreign.with_context(org_staff_sync=True, sports_staff_batch=True).write({"grant_id": False})
        touched = self._release_rows(rows - foreign)
        res = super().unlink()
        self.env["sports.organization.staff"]._apply_staff_side_effects(
            teams=touched["teams"], users=touched["users"],
            unlinked_teams=touched["unlinked_teams"],
        )
        return res

    # ------------------------------------------------------------------
    # reconciler
    # ------------------------------------------------------------------
    def _scope_teams(self):
        self.ensure_one()
        if self.scope == "team":
            return self.team_id
        return self.organization_id.with_context(active_test=False).owned_team_ids

    def _partner_eligible(self):
        """Same rule as the organization lines / archive purge: never
        materialize for an archived contact or a contact whose user accounts
        are all archived."""
        self.ensure_one()
        return self.env["sports.organization.staff"]._partner_active_for_staff(
            self.partner_id
        )

    def _state_at(self, now):
        self.ensure_one()
        if self.state == "revoked":
            return "revoked"
        if now < self.date_start:
            return "scheduled"
        if now < self.date_end:
            return "active"
        return "expired"

    def _reconcile(self, now=None):
        """Materialize / remove the temporary staff rows of these grants for
        the moment ``now`` (default: now; tests pass a moment to move the
        clock) and update their ``state``. Idempotent; runs sudo; batched side
        effects. Returns a counts dict."""
        now = now or fields.Datetime.now()
        OrgStaff = self.env["sports.organization.staff"]
        Staff = OrgStaff._staff_env()
        touched_teams = self.env["sports.team"].sudo()
        touched_users = self.env["res.users"].sudo()
        unlinked_teams = self.env["sports.team"].sudo()
        counts = {"activated": 0, "expired": 0, "revoked": 0,
                  "rows_created": 0, "rows_removed": 0}

        for grant in self.sudo().with_context(active_test=False):
            old_state = grant.state
            new_state = grant._state_at(now)
            partner = grant.partner_id
            scope_teams = grant._scope_teams()
            eligible = new_state == "active" and grant._partner_eligible()
            # The grant owns its temp rows only: a row taken over by manual /
            # organization staff is no longer ours (detach it, never release it).
            owned = grant.staff_ids.filtered(lambda r: r.source == "temp")
            foreign = grant.staff_ids - owned
            if foreign:
                foreign.with_context(org_staff_sync=True, sports_staff_batch=True).write({"grant_id": False})
            desired = Staff.browse()
            opened = self.env["sports.team"].sudo()
            covered = self.env["sports.team"].sudo()

            if eligible:
                existing = Staff.search([
                    ("partner_id", "=", partner.id),
                    ("team_id", "in", scope_teams.ids),
                ])
                by_team = {r.team_id.id: r for r in existing}
                for team in scope_teams:
                    row = by_team.get(team.id)
                    if row and row.source in ("manual", "org"):
                        covered |= team
                        continue
                    if row and row.source == "temp" and row.grant_id and row.grant_id != grant:
                        covered |= team
                        continue
                    if row:
                        # our own row, or an event-coverage row adopted by the
                        # grant (temporary_event_ids kept for the hand-back).
                        vals = {}
                        if row.role != grant.role:
                            vals["role"] = grant.role
                        if row.silent_notifications != grant.silent_notifications:
                            vals["silent_notifications"] = grant.silent_notifications
                        if row.source != "temp":
                            vals["source"] = "temp"
                        if row.grant_id != grant:
                            vals["grant_id"] = grant.id
                        if vals:
                            row.write(vals)
                            touched_teams |= team
                            touched_users |= row.user_ids
                            if "grant_id" in vals:
                                opened |= team
                    else:
                        row = Staff.create({
                            "team_id": team.id,
                            "partner_id": partner.id,
                            "role": grant.role,
                            "silent_notifications": grant.silent_notifications,
                            "source": "temp",
                            "grant_id": grant.id,
                            "is_auto_created": False,
                        })
                        counts["rows_created"] += 1
                        touched_teams |= team
                        touched_users |= row.user_ids
                        opened |= team
                    desired |= row

            stale = owned - desired
            removed_teams = self.env["sports.team"].sudo()
            if stale:
                released = self._release_rows(stale, now)
                removed_teams = released["teams"]
                touched_teams |= released["teams"]
                touched_users |= released["users"]
                unlinked_teams |= released["unlinked_teams"]
                counts["rows_removed"] += released["count"]

            # state + audit (ids, dates and staff names only — no PHI)
            if new_state != old_state:
                grant.with_context(staff_grant_reconcile=True).write({"state": new_state})
                key = {"active": "activated", "expired": "expired",
                       "revoked": "revoked"}.get(new_state)
                if key:
                    counts[key] += 1
            if new_state == "active" and (old_state != "active" or opened):
                grant._post_audit(
                    _("Temporary access opened for %(person)s (%(role)s) until %(end)s"),
                    opened=opened, covered=covered, eligible=eligible,
                )
            elif new_state in ("expired", "revoked") and (old_state != new_state or removed_teams):
                # « Revoke now » writes the state first (write hook -> here):
                # the transition is already done, the removed rows tell.
                grant._post_audit(
                    _("Temporary access ended (%(state)s) for %(person)s — rows removed")
                    if new_state == "expired" else
                    _("Temporary access revoked for %(person)s — rows removed"),
                    removed_teams=removed_teams or None,
                )
            elif new_state == "active" and not eligible and old_state == "active" and removed_teams:
                grant._post_audit(
                    _("Temporary access for %(person)s: contact archived — rows removed"),
                    removed_teams=removed_teams,
                )

        OrgStaff._apply_staff_side_effects(
            teams=touched_teams, users=touched_users, unlinked_teams=unlinked_teams
        )
        return counts

    def _release_rows(self, rows, now=None):
        """Hand back or remove temporary rows that the grant no longer wants.
        A row whose person is still assigned to an OPEN event on that team
        goes back to the event coverage (source event, therapist, silent) —
        precedence temp > event — otherwise it is unlinked in batch mode.
        Returns the teams / users the caller must run the side effects for."""
        now = now or fields.Datetime.now()
        OrgStaff = self.env["sports.organization.staff"]
        rows = rows.sudo().with_context(active_test=False).exists()
        result = {
            "teams": rows.mapped("team_id"),
            "users": rows.mapped("user_ids"),
            "unlinked_teams": self.env["sports.team"].sudo(),
            "count": 0,
        }
        to_unlink = self.env["sports.team.staff"].sudo()
        for row in rows:
            active_events = row.temporary_event_ids.filtered(
                lambda e: e._is_active_for_access(now)
            )
            if active_events:
                row.with_context(org_staff_sync=True, sports_staff_batch=True).write({
                    "source": "event",
                    "grant_id": False,
                    "is_auto_created": True,
                    "role": "therapist",
                    "silent_notifications": True,
                    "temporary_event_ids": [Command.set(active_events.ids)],
                })
            else:
                to_unlink |= row
        if to_unlink:
            result["count"] = len(to_unlink)
            t = OrgStaff._unlink_staff_rows(to_unlink)
            result["unlinked_teams"] = t["unlinked_teams"]
        return result

    def _post_audit(self, template, opened=None, covered=None, eligible=True,
                    removed_teams=None):
        self.ensure_one()
        roles = dict(self._fields["role"]._description_selection(self.env))
        states = dict(self._fields["state"]._description_selection(self.env))
        body = template % {
            "person": self.partner_id.display_name,
            "role": roles.get(self.role, self.role),
            "end": format_datetime(self.env, self.date_end, dt_format="short"),
            "state": states.get(self.state, self.state),
        }
        parts = [body]
        if opened:
            parts.append(_("Teams: %s") % ", ".join(opened.mapped("display_name")))
        if covered:
            parts.append(
                _("Already covered (manual / organization staff, no temporary row): %s")
                % ", ".join(covered.mapped("display_name"))
            )
        if not eligible and self.state == "active":
            parts.append(_("Contact archived / no active user: nothing materialized."))
        if removed_teams:
            parts.append(_("Teams: %s") % ", ".join(removed_teams.mapped("display_name")))
        parts.append(
            _("Grant #%(id)s · %(start)s → %(end)s")
            % {
                "id": self.id,
                "start": format_datetime(self.env, self.date_start, dt_format="short"),
                "end": format_datetime(self.env, self.date_end, dt_format="short"),
            }
        )
        self.with_context(mail_notrack=True).message_post(
            body=Markup("<br/>").join(escape(p) for p in parts),
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

    # ------------------------------------------------------------------
    # entry points
    # ------------------------------------------------------------------
    def action_revoke_now(self):
        """End the access immediately: state revoked, rows removed now (the
        write hook runs the reconcile for this grant)."""
        now = fields.Datetime.now()
        for grant in self:
            if grant.state in ("expired", "revoked"):
                raise UserError(
                    _("%s is already %s.")
                    % (grant.display_name,
                       dict(GRANT_STATES).get(grant.state, grant.state).lower())
                )
        self.write({
            "state": "revoked",
            "revoked_by_id": self.env.user.id,
            "revoked_on": now,
        })
        return True

    def action_reconcile_now(self):
        self._reconcile()
        return True

    def action_open_staff_rows(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Temporary Staff Rows"),
            "res_model": "sports.team.staff",
            "view_mode": "list,form",
            "domain": [("grant_id", "=", self.id)],
            "context": {"create": False},
        }

    @api.model
    def _reconcile_all(self, now=None):
        """Every grant that may need rows opened or closed: scheduled / active
        ones, plus expired / revoked ones that still own rows."""
        now = now or fields.Datetime.now()
        grants = self.sudo().search([("state", "in", ("scheduled", "active"))])
        grants |= self.sudo().search([("staff_ids", "!=", False)])
        # Two passes: grants that are NOT active at ``now`` release their rows
        # first, so a grant starting exactly when another ends takes the team
        # over in the same run (no one-hour hole — review finding).
        ending = grants.filtered(lambda g: g._state_at(now) != "active")
        counts = ending._reconcile(now)
        for key, value in (grants - ending)._reconcile(now).items():
            counts[key] = counts.get(key, 0) + value
        counts["grants"] = len(grants)
        return counts
