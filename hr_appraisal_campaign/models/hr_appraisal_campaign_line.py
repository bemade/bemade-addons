from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

# Stored grades and comments are readable only by HR and calibrators. Everyone else
# reads and writes them through the *_ui fields, whose compute/inverse apply the
# per-record rules of the evaluation (see hr.appraisal._campaign_roles).
PRIVATE_GROUPS = "hr_appraisal.group_hr_appraisal_user,hr_appraisal_campaign.group_campaign_calibration"


class HrAppraisalCampaignLine(models.Model):
    _name = "hr.appraisal.campaign.line"
    _description = "Evaluation Criterion Grade"
    _order = "appraisal_id, section_sequence, section_id, sequence, id"

    appraisal_id = fields.Many2one("hr.appraisal", required=True, ondelete="cascade", index=True)
    campaign_id = fields.Many2one(related="appraisal_id.campaign_id", store=True)
    employee_id = fields.Many2one(related="appraisal_id.employee_id", store=True)
    department_id = fields.Many2one(related="appraisal_id.department_id", store=True)
    job_id = fields.Many2one(related="appraisal_id.job_id", store=True)
    company_id = fields.Many2one(related="appraisal_id.company_id", store=True)
    evaluator_id = fields.Many2one(
        "hr.employee", "Evaluator", compute="_compute_evaluator", store=True)
    campaign_step = fields.Selection(related="appraisal_id.campaign_step")
    criterion_id = fields.Many2one(
        "hr.appraisal.campaign.criterion", "Catalogue Criterion", ondelete="set null")
    # frozen copy of the criterion, in every language
    section_id = fields.Many2one("hr.appraisal.campaign.section", "Section", ondelete="restrict")
    section_sequence = fields.Integer()
    sequence = fields.Integer()
    name = fields.Char("Criterion", translate=True)
    description = fields.Text(translate=True)
    level_text_ids = fields.One2many(
        "hr.appraisal.campaign.line.level", "line_id", "Word Pictures")
    levels_data = fields.Json(compute="_compute_levels_data")

    # private storage
    # grades aggregate with an average: a pivot cell (one line) shows the grade itself
    employee_grade = fields.Integer("Self Grade", groups=PRIVATE_GROUPS, aggregator="avg")
    employee_examples = fields.Text("Examples (employee)", groups=PRIVATE_GROUPS)
    manager_grade = fields.Integer("Manager Grade", groups=PRIVATE_GROUPS, aggregator="avg")
    manager_remarks = fields.Text("Manager Remarks", groups=PRIVATE_GROUPS)
    calibrated_grade = fields.Integer("Calibrated Grade", groups=PRIVATE_GROUPS, aggregator="avg")
    calibration_note = fields.Text(groups=PRIVATE_GROUPS)
    final_grade = fields.Integer(
        "Final Grade", compute="_compute_final_grade", store=True, groups=PRIVATE_GROUPS,
        aggregator="avg")
    final_vs_manager = fields.Integer(
        "Calibration Delta", compute="_compute_final_grade", store=True, groups=PRIVATE_GROUPS)
    calibration_log_ids = fields.One2many(
        "hr.appraisal.campaign.calibration.log", "line_id", groups=PRIVATE_GROUPS)
    remark_log_ids = fields.One2many(
        "hr.appraisal.campaign.remark.log", "line_id", "Remark Changes",
        groups="hr_appraisal.group_hr_appraisal_user")

    # per-user view of the private fields
    employee_grade_ui = fields.Integer(
        "Self Grade (shown)", compute="_compute_ui", inverse="_inverse_employee_ui")
    employee_examples_ui = fields.Text(
        "Examples", compute="_compute_ui", inverse="_inverse_employee_ui")
    manager_grade_ui = fields.Integer(
        "Manager Grade (shown)", compute="_compute_ui", inverse="_inverse_manager_grade_ui")
    manager_remarks_ui = fields.Text(
        "Remarks / Improvement", compute="_compute_ui", inverse="_inverse_manager_remarks_ui")
    final_grade_ui = fields.Integer("Final Grade (shown)", compute="_compute_ui")
    can_edit_employee = fields.Boolean(compute="_compute_ui")
    can_edit_manager = fields.Boolean(compute="_compute_ui")
    can_edit_remarks = fields.Boolean(compute="_compute_ui")
    can_see_employee = fields.Boolean(compute="_compute_ui")
    can_see_manager = fields.Boolean(compute="_compute_ui")

    _grades_positive = models.Constraint(
        "CHECK(employee_grade >= 0 AND manager_grade >= 0 AND calibrated_grade >= 0)",
        "Grades are levels of the rating scale.",
    )

    @api.depends("appraisal_id.manager_ids")
    def _compute_evaluator(self):
        for line in self:
            line.evaluator_id = line.appraisal_id.manager_ids[:1]

    @api.depends("level_text_ids.description", "level_text_ids.level_id")
    @api.depends_context("lang")
    def _compute_levels_data(self):
        for line in self:
            line.levels_data = [{
                "value": text.level_id.value,
                "name": text.level_id.name,
                "text": text.description or "",
                "color": text.level_id.display_color,
            } for text in line.sudo().level_text_ids.sorted("value")]

    @api.depends("manager_grade", "calibrated_grade")
    def _compute_final_grade(self):
        for line in self:
            line.final_grade = line.calibrated_grade or line.manager_grade
            line.final_vs_manager = (
                line.final_grade - line.manager_grade if line.manager_grade else 0)

    @api.depends(
        "employee_grade", "employee_examples", "manager_grade", "manager_remarks",
        "calibrated_grade", "appraisal_id.campaign_step", "appraisal_id.campaign_shared",
        "appraisal_id.employee_ack_date",
    )
    @api.depends_context("uid")
    def _compute_ui(self):
        roles_by_appraisal = {}
        for line in self:
            appraisal = line.appraisal_id
            if appraisal.id not in roles_by_appraisal:
                roles_by_appraisal[appraisal.id] = appraisal._campaign_roles()
            roles = roles_by_appraisal[appraisal.id]
            private = line.sudo()
            see_employee = roles["see_self"]
            see_manager = roles["see_manager"]
            line.can_see_employee = see_employee
            line.can_see_manager = see_manager
            line.can_edit_employee = roles["edit_self"]
            line.can_edit_manager = roles["edit_manager"]
            line.can_edit_remarks = roles["edit_remarks"]
            line.employee_grade_ui = private.employee_grade if see_employee else 0
            line.employee_examples_ui = private.employee_examples if see_employee else False
            line.manager_grade_ui = private.manager_grade if see_manager else 0
            line.manager_remarks_ui = private.manager_remarks if see_manager else False
            line.final_grade_ui = private.final_grade if see_manager else 0

    def _check_grade(self, grade):
        """0 (not graded) or a level of the campaign's scale."""
        for line in self:
            scale = line.sudo().appraisal_id.campaign_id.scale_id
            if grade and grade not in scale.level_ids.mapped("value"):
                raise ValidationError(self.env._(
                    "%(grade)s is not a level of the rating scale « %(scale)s ».",
                    grade=grade, scale=scale.display_name))

    def _inverse_employee_ui(self):
        for line in self:
            roles = line.appraisal_id._campaign_roles()
            if not roles["edit_self"]:
                raise AccessError(self.env._(
                    "You cannot change the self-evaluation of %s at this step.",
                    line.appraisal_id.sudo().employee_id.name))
            line._check_grade(line.employee_grade_ui)
            line.sudo().write({
                "employee_grade": line.employee_grade_ui,
                "employee_examples": line.employee_examples_ui,
            })

    def _inverse_manager_grade_ui(self):
        for line in self:
            roles = line.appraisal_id._campaign_roles()
            if not roles["edit_manager"]:
                raise AccessError(self.env._(
                    "You cannot change the manager evaluation of %s at this step.",
                    line.appraisal_id.sudo().employee_id.name))
            line._check_grade(line.manager_grade_ui)
            line.sudo().write({"manager_grade": line.manager_grade_ui})

    def _inverse_manager_remarks_ui(self):
        for line in self:
            line._campaign_check_can_edit_remarks()
            old = {line.id: line.sudo().manager_remarks}
            line.sudo().write({"manager_remarks": line.manager_remarks_ui})
            line._campaign_log_remarks(old)

    def _campaign_check_can_edit_remarks(self):
        for line in self:
            if not line.appraisal_id._campaign_roles()["edit_remarks"]:
                raise AccessError(self.env._(
                    "You cannot change the remarks of %s at this step: the evaluator edits them "
                    "until the employee acknowledges the evaluation.",
                    line.appraisal_id.sudo().employee_id.name))

    def _campaign_log_remarks(self, old):
        """Log remark changes made after « Submit for Calibration » (``old``: id → text)."""
        Log = self.env["hr.appraisal.campaign.remark.log"].sudo()
        for line in self.sudo():
            step = line.appraisal_id.campaign_step
            if step in ("calibration", "meeting") and (old[line.id] or "") != (line.manager_remarks or ""):
                Log.create({
                    "line_id": line.id,
                    "user_id": self.env.uid,
                    "step": step,
                    "old_remarks": old[line.id],
                    "new_remarks": line.manager_remarks,
                })

    def action_campaign_open_calibration_log(self):
        """The change log of this grade (from the calibration list)."""
        self.ensure_one()
        title = self.env._("Calibration Changes")
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": "hr.appraisal.campaign.calibration.log",
            "view_mode": "list",
            "domain": [("line_id", "=", self.id)],
            "target": "new",
        }

    # ------------------------------------------------------------------ write guard
    _UI_FIELDS = {
        "employee_grade_ui", "employee_examples_ui", "manager_grade_ui", "manager_remarks_ui",
    }
    _CALIBRATION_FIELDS = {"calibrated_grade", "calibration_note"}

    def write(self, vals):
        if self.env.su:
            return super().write(vals)
        if any(line.appraisal_id.campaign_step == "closed" for line in self):
            raise UserError(self.env._("A closed evaluation cannot be changed."))
        keys = set(vals)
        is_hr = self.env.user.has_group("hr_appraisal.group_hr_appraisal_user")
        if not is_hr and keys - self._UI_FIELDS - self._CALIBRATION_FIELDS:
            raise AccessError(self.env._("Evaluation lines are changed from the evaluation form."))
        if "manager_grade" in keys and any(
            line.appraisal_id.campaign_step not in (False, "self_eval", "manager_eval") for line in self
        ):
            raise UserError(self.env._(
                "The manager's grades are locked once submitted for calibration; "
                "only the calibrated grade can change, during the calibration."))
        if "manager_remarks" in keys:
            self._campaign_check_can_edit_remarks()
            old = {line.id: line.sudo().manager_remarks for line in self}
            res = super().write(vals)
            self._campaign_log_remarks(old)
            return res
        if keys & self._CALIBRATION_FIELDS:
            self._check_can_calibrate()
            old = {line.id: line.sudo().calibrated_grade for line in self}
            res = super().write(vals)
            for line in self.sudo():
                if not line.calibration_note and line.calibrated_grade != line.manager_grade:
                    raise ValidationError(self.env._(
                        "Explain the calibration of « %s » in the calibration note.", line.name))
                if "calibrated_grade" in vals and old[line.id] != line.calibrated_grade:
                    line._check_grade(line.calibrated_grade)
                    self.env["hr.appraisal.campaign.calibration.log"].sudo().create({
                        "line_id": line.id,
                        "user_id": self.env.uid,
                        "old_grade": old[line.id],
                        "new_grade": line.calibrated_grade,
                        "note": line.calibration_note,
                    })
            return res
        for fname in ("employee_grade", "manager_grade"):
            if vals.get(fname):
                self._check_grade(vals[fname])
        return super().write(vals)

    def _check_can_calibrate(self):
        is_hr = self.env.user.has_group("hr_appraisal.group_hr_appraisal_user")
        is_cal = self.env.user.has_group("hr_appraisal_campaign.group_campaign_calibration")
        for line in self:
            appraisal = line.appraisal_id.sudo()
            if not (is_hr or is_cal):
                raise AccessError(self.env._("Only calibrators adjust grades."))
            if appraisal.employee_id.user_id == self.env.user:
                raise AccessError(self.env._("You cannot calibrate your own evaluation."))
            if appraisal.campaign_step != "calibration" or (
                appraisal.campaign_id and appraisal.campaign_id.state != "calibration"
            ):
                raise UserError(self.env._(
                    "Grades of %s can only be calibrated during the calibration phase.",
                    appraisal.employee_id.name))


class HrAppraisalCampaignLineLevel(models.Model):
    """Frozen word picture of one level of a graded criterion."""

    _name = "hr.appraisal.campaign.line.level"
    _description = "Evaluation Criterion Grade Word Picture"
    _order = "line_id, value, id"

    line_id = fields.Many2one(
        "hr.appraisal.campaign.line", required=True, ondelete="cascade", index=True)
    level_id = fields.Many2one(
        "hr.appraisal.campaign.scale.level", "Level", required=True, ondelete="restrict")
    value = fields.Integer(related="level_id.value", store=True)
    description = fields.Text("Word Picture", translate=True)
