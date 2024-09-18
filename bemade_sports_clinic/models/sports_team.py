from odoo import models, fields, api, _, Command
from odoo.exceptions import ValidationError


class SportsTeam(models.Model):
    _name = "sports.team"
    _description = "Sports Team"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char()
    patient_ids = fields.Many2many(
        comodel_name="sports.patient",
        relation="sports_team_patient_rel",
        column1="team_id",
        column2="patient_id",
        string="Players",
        tracking=True,
    )
    player_count = fields.Integer(compute="_compute_player_counts")
    injured_count = fields.Integer(compute="_compute_player_counts")
    healthy_count = fields.Integer(compute="_compute_player_counts")
    parent_id = fields.Many2one(
        comodel_name="res.partner",
        string="Parent Organization",
        ondelete="restrict",
        tracking=True,
    )
    staff_ids = fields.One2many(
        comodel_name="sports.team.staff",
        inverse_name="team_id",
        tracking=True,
    )
    head_coach_id = fields.Many2one(
        comodel_name="res.partner",
        compute="_compute_head_coach",
        store=True,
    )
    head_coach_name = fields.Char(
        related="head_coach_id.name",
        string="Head Coach Name",
    )
    head_therapist_id = fields.Many2one(
        comodel_name="res.partner",
        compute="_compute_head_therapist",
        store=True,
        string="Head Therapist",
    )
    head_therapist_name = fields.Char(
        related="head_therapist_id.name",
        string="Head Therapist Name",
    )
    website = fields.Char()
    allowed_user_ids = fields.Many2many(
        comodel_name="res.users",
        compute="_compute_allowed_user_ids",
        inverse="_inverse_allowed_user_ids",
    )

    def write(self, vals):
        previous_patient_ids = self.sudo().patient_ids
        res = super().write(vals)
        if "staff_ids" in vals or "patient_ids" in vals:
            (self.sudo().patient_ids | previous_patient_ids).recompute_followers()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for index, rec in enumerate(res):
            if "staff_ids" in vals_list[index]:
                rec.sudo()._allow_access_for_staff_internal_users()
                rec.sudo().patient_ids.recompute_followers()
        return res

    def unlink(self):
        to_recompute = self.patient_ids
        res = super().unlink()
        to_recompute.recompute_followers()
        return res

    @api.depends("patient_ids.is_injured")
    def _compute_player_counts(self):
        for rec in self:
            rec.player_count = len(rec.patient_ids)
            rec.injured_count = len(rec.patient_ids.filtered(lambda p: p.is_injured))
            rec.healthy_count = rec.player_count - rec.injured_count

    @api.depends("staff_ids.role")
    def _compute_head_coach(self):
        for rec in self:
            staff = rec.staff_ids.filtered(lambda r: r.role == "head_coach")
            rec.head_coach_id = staff.partner_id if staff else False

    @api.depends("staff_ids.role")
    def _compute_head_therapist(self):
        for rec in self:
            staff = rec.staff_ids.filtered(lambda r: r.role == "head_therapist")
            rec.head_therapist_id = staff.partner_id if staff else False

    def _compute_allowed_user_ids(self):
        for rec in self:
            rec.allowed_user_ids = rec.staff_ids.user_ids

    def _inverse_allowed_user_ids(self):
        for rec in self:
            removed_staff = rec.staff_ids.filtered(
                lambda staff: staff.user_ids not in rec.allowed_user_ids
            )
            added_users = rec.allowed_user_ids - rec.staff_ids.user_ids
            removed_staff.unlink()
            self.env["sports.team.staff"].create(
                [
                    {
                        "team_id": rec.id,
                        "partner_id": user.partner_id.id,
                        "role": "other",
                    }
                    for user in added_users
                ]
            )


class TeamStaff(models.Model):
    _name = "sports.team.staff"
    _description = "Sports Team Staff"

    sequence = fields.Integer()
    team_id = fields.Many2one(
        comodel_name="sports.team",
        string="Team",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Staff Member",
        required=True,
        domain=[("is_company", "=", False)],
        ondelete="cascade",
    )
    active = fields.Boolean(related="partner_id.active")
    role = fields.Selection(
        selection=[
            ("head_coach", "Head Coach"),
            ("head_therapist", "Head Therapist"),
            ("coach", "Coach"),
            ("therapist", "Therapist"),
            ("doctor", "Doctor"),
            ("other", "Other"),
        ],
        required=True,
    )
    mobile = fields.Char(related="partner_id.mobile", readonly=False)
    name = fields.Char(related="partner_id.name", readonly=False)
    parent_id = fields.Many2one(
        related="partner_id.parent_id",
        readonly=False,
        string="Organization",
        domain=[("is_company", "=", True)],
    )
    email = fields.Char(related="partner_id.email", readonly=False)
    user_ids = fields.One2many(related="partner_id.user_ids", readonly=True)
    has_portal_access = fields.Boolean(
        compute="_compute_has_portal_access", compute_sudo=True
    )

    _sql_constraints = [
        (
            "team_staff_unique",
            "unique(team_id, partner_id)",
            "Each partner can only be related to a given team once.",
        )
    ]

    @api.constrains("role")
    def _constrain_role(self):
        teams = self.mapped("team_id")
        for team in teams:
            if len(team.staff_ids.filtered(lambda r: r.role == "head_coach")) > 1:
                raise ValidationError(_("A team can have only one head coach."))
            if len(team.staff_ids.filtered(lambda r: r.role == "head_therapist")) > 1:
                raise ValidationError(_("A team can have only one head therapist."))

    @api.onchange("mobile")
    def _onchange_mobile_validation(self):
        if self.mobile:
            self.mobile = self.partner_id._phone_format(
                self.mobile, force_format="INTERNATIONAL"
            )

    @api.depends("user_ids", "user_ids.groups_id")
    def _compute_has_portal_access(self):
        for rec in self:
            rec.has_portal_access = (
                bool(rec.user_ids.filtered(lambda r: r.has_group("base.group_portal")))
                or bool(rec.user_ids.filtered(lambda r: r.has_group("base.group_user")))
                or bool(rec.partner_id.signup_token)
            )

    def action_revoke_portal_access(self):
        group_portal = self.env.ref("base.group_portal")
        group_public = self.env.ref("base.group_public")
        self.user_ids.write(
            {
                "groups_id": [
                    Command.unlink(group_portal.id),
                    Command.link(group_public.id),
                ],
                "active": False,
            }
        )
        # Remove the signup token, so it cannot be used
        self.partner_id.sudo().signup_token = False

    def action_grant_portal_access(self):
        wiz = self.env["portal.wizard"].create(
            {"partner_ids": [(4, self.partner_id.id)]}
        )
        return wiz._action_open_modal()

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res.team_id.mapped("patient_ids").recompute_followers()
        return res

    def unlink(self):
        patients = self.team_id.mapped("patient_ids")
        super().unlink()
        patients.recompute_followers()

    def write(self, values):
        if "team_id" in values:
            to_recompute = self.env["sports.patient"]
            for rec in self:
                if rec.team_id.id != values["team_id"]:
                    to_recompute |= rec.team_id.patient_ids
            res = super().write(values)
            to_recompute.recompute_followers()
            return res
        return super().write(values)
