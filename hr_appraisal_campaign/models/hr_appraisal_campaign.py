from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

STEPS = [
    ("self_eval", "Self-evaluation"),
    ("manager_eval", "Manager evaluation"),
    ("calibration", "Calibration"),
    ("meeting", "Meeting"),
    ("acknowledged", "Acknowledged"),
    ("closed", "Closed"),
]


class HrAppraisalCampaign(models.Model):
    _name = "hr.appraisal.campaign"
    _description = "Evaluation Campaign"
    _inherit = ["mail.thread"]
    _order = "date_start desc, id desc"

    name = fields.Char(required=True, tracking=True, help="e.g. Annual 2026")
    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company)
    user_id = fields.Many2one(
        "res.users", "HR Responsible", default=lambda s: s.env.user, tracking=True,
        help="Receives the HR to-dos of the campaign (appraisals to close).",
    )
    date_start = fields.Date("Period Start", required=True, default=fields.Date.context_today)
    date_end = fields.Date("Period End")
    deadline_self_eval = fields.Date("Self-evaluation Deadline")
    deadline_manager = fields.Date("Manager Evaluation Deadline")
    deadline_calibration = fields.Date("Calibration Deadline")
    deadline_meetings = fields.Date("Meetings Deadline")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("running", "Running"),
            ("calibration", "Calibration"),
            ("meetings", "Meetings"),
            ("closed", "Closed"),
        ],
        default="draft", required=True, tracking=True, copy=False,
    )
    scale_id = fields.Many2one(
        "hr.appraisal.campaign.scale", "Rating Scale", required=True, ondelete="restrict",
        default=lambda s: s.env["hr.appraisal.campaign.scale"].search([], limit=1), tracking=True)
    section_ids = fields.Many2many(
        "hr.appraisal.campaign.section", compute="_compute_section_ids", string="Sections")
    employee_ids = fields.Many2many(
        "hr.employee", string="Employees",
        help="Employees evaluated in this campaign. Employees without an Odoo user are "
        "listed for HR to handle on paper.",
    )
    employee_without_user_ids = fields.Many2many(
        "hr.employee", compute="_compute_employee_warnings", string="Employees Without User")
    employee_without_manager_ids = fields.Many2many(
        "hr.employee", compute="_compute_employee_warnings", string="Employees Without Manager")
    appraisal_ids = fields.One2many("hr.appraisal", "campaign_id", "Appraisals")
    appraisal_count = fields.Integer(compute="_compute_step_counts")
    count_self_eval = fields.Integer("To self-evaluate", compute="_compute_step_counts")
    count_manager_eval = fields.Integer("To evaluate (manager)", compute="_compute_step_counts")
    count_calibration = fields.Integer("In calibration", compute="_compute_step_counts")
    count_meeting = fields.Integer("Meeting", compute="_compute_step_counts")
    count_acknowledged = fields.Integer("Acknowledged", compute="_compute_step_counts")
    count_closed = fields.Integer("Closed", compute="_compute_step_counts")
    count_overdue = fields.Integer("Overdue", compute="_compute_step_counts")

    # scoring rules of the campaign (copied from the scale and sections at creation)
    threshold_ids = fields.One2many(
        "hr.appraisal.campaign.threshold", "campaign_id", "Thresholds", copy=True)
    target_score = fields.Integer(
        "Target Score", compute="_compute_scoring_defaults", store=True, readonly=False,
        precompute=True, help="Overall points the company expects (shown on the evaluation).")
    alignment_gap = fields.Integer(
        "Alignment Gap", compute="_compute_scoring_defaults", store=True, readonly=False,
        precompute=True,
        help="Self and final totals within this many points are « aligned »; beyond, the "
        "gap is to be discussed in the meeting.",
    )

    # ------------------------------------------------------------------ wording hooks
    @api.model
    def _campaign_render_text(self, render, users=None):
        """Text the system writes by itself (to-do summary): ``render(env)`` translates
        with ``env._``. Rendered in the recipient's language. Override to change it
        (e.g. several languages)."""
        lang = (users[:1].lang if users else None) or self.env.lang
        return render(self.env(context=dict(self.env.context, lang=lang)))

    @api.model
    def _campaign_render_html(self, render, users=None):
        """Same as ``_campaign_render_text`` for HTML (to-do notes, chatter notes)."""
        return Markup("<p>%s</p>") % self._campaign_render_text(render, users)

    def _creation_message(self):
        return self._campaign_render_html(lambda env: env._("Evaluation campaign created"))

    # ------------------------------------------------------------------ computes
    @api.depends("scale_id")
    def _compute_section_ids(self):
        for campaign in self:
            campaign.section_ids = campaign.scale_id.section_ids

    @api.depends("scale_id")
    def _compute_scoring_defaults(self):
        for campaign in self:
            campaign.target_score = campaign.scale_id.default_target_score
            campaign.alignment_gap = campaign.scale_id.default_alignment_gap

    @api.depends("employee_ids")
    def _compute_employee_warnings(self):
        for campaign in self:
            employees = campaign.employee_ids.sudo()
            campaign.employee_without_user_ids = employees.filtered(lambda e: not e.user_id)
            campaign.employee_without_manager_ids = employees.filtered(lambda e: not e.parent_id)

    def _compute_step_counts(self):
        today = fields.Date.context_today(self)
        for campaign in self:
            appraisals = campaign.appraisal_ids
            campaign.appraisal_count = len(appraisals)
            for step, _label in STEPS:
                campaign[f"count_{step}"] = len(
                    appraisals.filtered(lambda a, s=step: a.campaign_step == s))
            campaign.count_overdue = len(
                appraisals.filtered(lambda a: a.campaign_deadline and a.campaign_deadline < today))

    # ------------------------------------------------------------------ thresholds
    def _default_threshold_commands(self):
        """Copy of the scale's overall and its sections' default thresholds."""
        self.ensure_one()
        defaults = self.scale_id.threshold_ids | self.scale_id.section_ids.threshold_ids
        return [Command.create({
            "section_id": t.section_id.id,
            "scale_id": t.scale_id.id,
            "level_id": t.level_id.id,
            "min_score": t.min_score,
        }) for t in defaults.filtered(lambda t: not t.campaign_id)]

    @api.onchange("scale_id")
    def _onchange_scale_id_thresholds(self):
        if self.state == "draft" and self.scale_id:
            self.threshold_ids = [Command.clear()] + self._default_threshold_commands()

    @api.model_create_multi
    def create(self, vals_list):
        campaigns = super().create(vals_list)
        for campaign, vals in zip(campaigns, vals_list):
            if not vals.get("threshold_ids") and campaign.scale_id:
                campaign.threshold_ids = campaign._default_threshold_commands()
        return campaigns

    def action_reset_thresholds(self):
        for campaign in self:
            if campaign.state != "draft":
                raise UserError(self.env._("Thresholds are reloaded before the launch only."))
            campaign.threshold_ids = [Command.clear()] + campaign._default_threshold_commands()

    def _campaign_band(self, score, section=None):
        """The rating level ``score`` reaches: the highest level whose threshold it
        reaches, else the lowest level of the scale; no thresholds → empty."""
        self.ensure_one()
        Level = self.env["hr.appraisal.campaign.scale.level"]
        section = section or self.env["hr.appraisal.campaign.section"]
        rules = self.sudo().threshold_ids.filtered(lambda t: t.section_id == section)
        if not rules:
            return Level
        for rule in rules.sorted(lambda t: (t.min_score, t.level_id.value), reverse=True):
            if score >= rule.min_score:
                return rule.level_id
        return self.sudo().scale_id._lowest_level()

    # ------------------------------------------------------------------ actions
    def action_load_employees(self):
        """Fill the campaign with every active employee of the company."""
        for campaign in self:
            employees = self.env["hr.employee"].search([("company_id", "=", campaign.company_id.id)])
            campaign.employee_ids = [Command.set(employees.ids)]

    def _campaign_criteria(self):
        self.ensure_one()
        return self.env["hr.appraisal.campaign.criterion"].search([
            ("scale_id", "=", self.scale_id.id),
            ("section_id.active", "=", True),
        ])

    def action_launch(self):
        for campaign in self:
            if campaign.state != "draft":
                raise UserError(self.env._("Only a draft campaign can be launched."))
            employees = campaign.employee_ids.sudo().filtered("user_id")
            if not employees:
                raise UserError(self.env._("Add the employees (with an Odoo user) to evaluate."))
            if campaign.scale_id.level_count < 2:
                raise UserError(self.env._("The rating scale needs at least two levels."))
            criteria = campaign._campaign_criteria()
            if not criteria:
                raise UserError(self.env._("The criteria catalogue of this scale is empty."))
            incomplete = criteria._missing_pictures()
            if incomplete:
                raise UserError(self.env._(
                    "Give every criterion a word picture for each level of the scale: %s",
                    ", ".join(incomplete.mapped("name"))))
            vals_list = [{
                "employee_id": employee.id,
                "manager_ids": [Command.set(employee.parent_id.ids)],
                "company_id": employee.company_id.id,
                "date_close": campaign.deadline_meetings or campaign.date_end
                or fields.Date.context_today(self),
                "campaign_id": campaign.id,
                "campaign_step": "self_eval",
            } for employee in employees]
            appraisals = self.env["hr.appraisal"].sudo().with_context(
                campaign_launch=True).create(vals_list)
            appraisals._campaign_freeze_criteria(criteria)
            campaign.state = "running"
            for appraisal in appraisals:
                appraisal._campaign_schedule(
                    appraisal.employee_id.user_id,
                    lambda env: env._("Complete your self-evaluation"),
                    campaign.deadline_self_eval,
                )
        return True

    def action_start_calibration(self):
        self.filtered(lambda c: c.state == "running").state = "calibration"

    def action_close_calibration(self):
        for campaign in self:
            if campaign.state != "calibration":
                raise UserError(self.env._("The campaign is not in calibration."))
            campaign.state = "meetings"
            to_meet = campaign.appraisal_ids.filtered(lambda a: a.campaign_step == "calibration")
            to_meet._campaign_to_meeting()

    def action_close(self):
        for campaign in self:
            open_ones = campaign.appraisal_ids.filtered(
                lambda a: a.campaign_step != "closed" and a.active)
            if open_ones:
                raise UserError(self.env._(
                    "%(count)s evaluations are not closed yet.", count=len(open_ones)))
            campaign.state = "closed"

    def action_open_appraisals(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "hr_appraisal_campaign.action_campaign_appraisals")
        action["domain"] = [("campaign_id", "=", self.id)]
        action["context"] = {"default_campaign_id": self.id, "search_default_group_campaign_step": 1}
        return action

    def action_open_calibration_board(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "hr_appraisal_campaign.action_campaign_calibration_board")
        action["domain"] = [("campaign_id", "=", self.id)]
        return action
