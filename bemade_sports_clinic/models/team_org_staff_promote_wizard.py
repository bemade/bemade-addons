"""Task 1415 — promotion wizard: turn existing per-team staff rows into
organization staff lines, WITHOUT deleting / recreating rows.

Opened from the organization partner form. Proposes every person holding a
hand-made (``manual``) staff row on at least ``threshold`` % of the
organization's teams: dominant role, silent majority, the teams where the
role differs (proposed overrides) and the teams missing. Nothing is written
until « Apply »: the wizard IS the dry run. Apply creates the organization
lines (+ overrides), re-sources the existing rows (``source='org'``,
``org_staff_line_id``) so followers / activities / groups are untouched, then
runs the reconciler to add the missing teams.
"""
from collections import Counter, defaultdict

from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError

from .sports_organization_staff import STAFF_ROLES


class TeamOrgStaffPromoteWizard(models.TransientModel):
    _name = "team.org.staff.promote.wizard"
    _description = "Promote team staff to organization staff"

    organization_id = fields.Many2one(
        comodel_name="res.partner",
        string="Organization",
        required=True,
        readonly=True,
        domain=[("is_company", "=", True)],
    )
    threshold = fields.Float(
        string="Minimum coverage (%)",
        default=80.0,
        help="Only people holding a manual staff row on at least this share "
             "of the organization's teams are proposed.",
    )
    team_count = fields.Integer(
        string="Teams in organization", compute="_compute_team_count"
    )
    line_ids = fields.One2many(
        comodel_name="team.org.staff.promote.wizard.line",
        inverse_name="wizard_id",
        string="Proposals",
    )
    summary = fields.Char(compute="_compute_summary")

    @api.depends("organization_id")
    def _compute_team_count(self):
        for wiz in self:
            wiz.team_count = len(wiz._org_teams())

    @api.depends("line_ids.selected", "line_ids.row_count", "line_ids.missing_count")
    def _compute_summary(self):
        for wiz in self:
            sel = wiz.line_ids.filtered("selected")
            wiz.summary = _(
                "%(people)s person(s) selected: %(rows)s existing row(s) will be "
                "re-sourced as Organization (no deletion), %(missing)s row(s) "
                "created on the missing teams, %(overrides)s role override(s)."
            ) % {
                "people": len(sel),
                "rows": sum(sel.mapped("row_count")),
                "missing": sum(sel.mapped("missing_count")),
                "overrides": sum(sel.mapped("override_count")),
            }

    def _org_teams(self):
        self.ensure_one()
        return self.organization_id.sudo().with_context(active_test=False).owned_team_ids

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        org_id = self.env.context.get("default_organization_id") or self.env.context.get(
            "active_id"
        )
        org = self.env["res.partner"].browse(org_id) if org_id else None
        if not org or not org.exists() or not org.is_company:
            raise UserError(_("Open this wizard from an organization (company contact)."))
        threshold = res.get("threshold") or 80.0
        res.update(
            {
                "organization_id": org.id,
                "line_ids": self._build_lines(org, threshold),
            }
        )
        return res

    @api.model
    def _build_lines(self, org, threshold):
        """Proposal lines as O2m commands (the dry run)."""
        teams = org.sudo().with_context(active_test=False).owned_team_ids
        if not teams:
            return []
        Staff = self.env["sports.team.staff"].sudo().with_context(active_test=False)
        rows = Staff.search(
            [("team_id", "in", teams.ids), ("source", "=", "manual")]
        )
        already = self.env["sports.organization.staff"].sudo().with_context(
            active_test=False
        ).search([("organization_id", "=", org.id)]).mapped("partner_id")
        by_partner = defaultdict(lambda: Staff.browse())
        for row in rows:
            by_partner[row.partner_id] |= row
        need = len(teams) * (threshold or 0.0) / 100.0
        commands = []
        for partner, prow in sorted(
            by_partner.items(), key=lambda kv: (-len(kv[1]), kv[0].display_name or "")
        ):
            if partner in already:
                continue
            if len(prow) < need or not prow:
                continue
            roles = Counter(prow.mapped("role"))
            order = [r for r, _l in STAFF_ROLES]
            role = sorted(roles.items(), key=lambda kv: (-kv[1], order.index(kv[0])))[0][0]
            silent = len(prow.filtered("silent_notifications")) * 2 > len(prow)
            off = prow.filtered(lambda r: r.role != role)
            missing = teams - prow.mapped("team_id")
            commands.append(
                Command.create(
                    {
                        "selected": True,
                        "partner_id": partner.id,
                        "role": role,
                        "silent_notifications": silent,
                        "row_count": len(prow),
                        "coverage": 100.0 * len(prow) / len(teams),
                        "override_count": len(off),
                        "override_data": {str(r.team_id.id): r.role for r in off},
                        "override_summary": ", ".join(
                            "%s → %s" % (r.team_id.display_name, dict(STAFF_ROLES).get(r.role, r.role))
                            for r in off.sorted(lambda r: r.team_id.display_name or "")
                        ),
                        "missing_count": len(missing),
                        "missing_team_ids": [Command.set(missing.ids)],
                        "missing_summary": ", ".join(
                            missing.sorted(lambda t: t.display_name or "").mapped("display_name")
                        ),
                    }
                )
            )
        return commands

    def action_refresh(self):
        """Rebuild the proposals with the current threshold (dry run)."""
        self.ensure_one()
        self.line_ids.unlink()
        self.write({"line_ids": self._build_lines(self.organization_id, self.threshold)})
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_apply(self):
        self.ensure_one()
        if not (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group("bemade_sports_clinic.group_sports_clinic_admin")
        ):
            raise UserError(_("Only administrators can promote staff to the organization."))
        selected = self.line_ids.filtered("selected")
        if not selected:
            raise UserError(_("Select at least one person to promote."))
        Line = self.env["sports.organization.staff"].sudo()
        Staff = self.env["sports.team.staff"].sudo().with_context(
            org_staff_sync=True, sports_staff_batch=True, active_test=False
        )
        teams = self._org_teams()
        created = Line.browse()
        for wl in selected:
            overrides = wl.override_data or {}
            line = Line.with_context(org_staff_skip_sync=True).create(
                {
                    "organization_id": self.organization_id.id,
                    "partner_id": wl.partner_id.id,
                    "role": wl.role,
                    "silent_notifications": wl.silent_notifications,
                    "override_ids": [
                        Command.create({"team_id": int(tid), "role": role})
                        for tid, role in overrides.items()
                        if int(tid) in teams.ids
                    ],
                }
            )
            # Re-source the existing rows in place: no unlink / create, so no
            # follower churn, no activity cleanup, ids and chatter untouched.
            rows = Staff.search(
                [
                    ("partner_id", "=", wl.partner_id.id),
                    ("team_id", "in", teams.ids),
                    ("source", "=", "manual"),
                ]
            )
            if rows:
                rows.write({"source": "org", "org_staff_line_id": line.id})
            created |= line
        # The reconciler adds the missing teams (and re-applies silent / role
        # where the proposal differs from a row), batching the side effects.
        created._sync()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Organization staff"),
                "message": _("%s person(s) promoted to the organization's staff.")
                % len(created),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }


class TeamOrgStaffPromoteWizardLine(models.TransientModel):
    _name = "team.org.staff.promote.wizard.line"
    _description = "Promote team staff to organization staff — line"
    _order = "row_count desc, id"

    wizard_id = fields.Many2one(
        comodel_name="team.org.staff.promote.wizard", required=True, ondelete="cascade"
    )
    selected = fields.Boolean(string="Promote", default=True)
    partner_id = fields.Many2one(
        comodel_name="res.partner", string="Staff Member", required=True, readonly=True
    )
    role = fields.Selection(selection=STAFF_ROLES, string="Dominant Role", required=True)
    silent_notifications = fields.Boolean(string="No Notifications")
    row_count = fields.Integer(string="Teams (existing rows)", readonly=True)
    coverage = fields.Float(string="Coverage (%)", readonly=True)
    override_count = fields.Integer(string="Overrides", readonly=True)
    override_data = fields.Json(readonly=True)
    override_summary = fields.Char(string="Proposed overrides", readonly=True)
    missing_count = fields.Integer(string="Missing teams", readonly=True)
    missing_team_ids = fields.Many2many(
        comodel_name="sports.team",
        relation="team_org_staff_promote_line_missing_team_rel",
        column1="line_id",
        column2="team_id",
        string="Teams without a row",
        readonly=True,
    )
    missing_summary = fields.Char(string="Missing teams (names)", readonly=True)
