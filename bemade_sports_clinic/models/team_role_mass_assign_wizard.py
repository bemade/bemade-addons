from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TeamRoleMassAssignWizard(models.TransientModel):
    _name = "team.role.mass.assign.wizard"
    _description = "Mass assign team roles to a user across teams"

    user_id = fields.Many2one("res.users", required=True, readonly=True)
    partner_id = fields.Many2one(
        "res.partner", related="user_id.partner_id", readonly=True, store=False
    )
    bulk_role = fields.Selection(
        selection=[
            ("head_coach", "Head Coach"),
            ("head_therapist", "Head Therapist"),
            ("coach", "Coach"),
            ("therapist", "Therapist"),
            ("doctor", "Doctor"),
            ("other", "Other"),
        ],
        string="Set role for selected",
        help="Pick a role to apply to all selected teams (and as default for newly selected teams).",
    )
    line_ids = fields.One2many(
        "team.role.mass.assign.line",
        "wizard_id",
        string="Teams",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        user = self.env["res.users"].browse(self.env.context.get("default_user_id"))
        if not user or not user.exists():
            raise UserError(_("Wizard must be opened from a user."))
        partner = user.partner_id
        Team = self.env["sports.team"].sudo()
        Staff = self.env["sports.team.staff"].sudo()
        lines = []
        # Prefetch existing staff roles for the partner
        staff_by_team = {
            s.team_id.id: s for s in Staff.search([("partner_id", "=", partner.id)])
        }
        for team in Team.search([], order="name"):
            staff = staff_by_team.get(team.id)
            lines.append(
                (
                    0,
                    0,
                    {
                        "team_id": team.id,
                        "selected": bool(staff),
                        "role": staff.role if staff else False,
                    },
                )
            )
        res.update({
            "user_id": user.id,
            "line_ids": lines,
        })
        return res

    @api.onchange("bulk_role")
    def _onchange_bulk_role(self):
        if not self.bulk_role:
            return
        for line in self.line_ids:
            if line.selected:
                line.role = self.bulk_role

    def action_apply(self):
        self.ensure_one()
        if not self.user_id or not self.partner_id:
            raise UserError(_("No target user provided."))
        Staff = self.env["sports.team.staff"].sudo()
        partner = self.partner_id
        # Apply selections
        for line in self.line_ids:
            if not line.selected:
                continue
            if not line.role:
                # If not specified but bulk_role exists, use it
                role = self.bulk_role
                if not role:
                    raise UserError(
                        _("Please choose a role for team '%s' or set a bulk role.") % (line.team_id.display_name,)
                    )
            else:
                role = line.role
            # Upsert staff record
            staff = Staff.search([
                ("team_id", "=", line.team_id.id),
                ("partner_id", "=", partner.id),
            ], limit=1)
            if staff:
                staff.write({"role": role})
            else:
                Staff.create({
                    "team_id": line.team_id.id,
                    "partner_id": partner.id,
                    "role": role,
                })
        # Do not remove existing team assignments that were unselected - explicit non-destructive behavior
        return {"type": "ir.actions.act_window_close"}


class TeamRoleMassAssignLine(models.TransientModel):
    _name = "team.role.mass.assign.line"
    _description = "Mass assign team roles - line"

    wizard_id = fields.Many2one("team.role.mass.assign.wizard", required=True, ondelete="cascade")
    selected = fields.Boolean(string="Assign")
    team_id = fields.Many2one("sports.team", required=True, ondelete="restrict")
    role = fields.Selection(
        selection=[
            ("head_coach", "Head Coach"),
            ("head_therapist", "Head Therapist"),
            ("coach", "Coach"),
            ("therapist", "Therapist"),
            ("doctor", "Doctor"),
            ("other", "Other"),
        ],
        string="Role",
    )

    @api.onchange("selected")
    def _onchange_selected(self):
        # If user toggles selection on and no role set yet, use wizard bulk role as default
        if self.selected and not self.role and self.wizard_id.bulk_role:
            self.role = self.wizard_id.bulk_role
