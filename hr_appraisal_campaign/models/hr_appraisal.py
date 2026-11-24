import base64

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .hr_appraisal_campaign import STEPS
from .hr_appraisal_campaign_line import PRIVATE_GROUPS

ODOO_STATE_BY_STEP = {
    "self_eval": "1_new",
    "manager_eval": "2_pending",
    "calibration": "2_pending",
    "meeting": "2_pending",
    "acknowledged": "2_pending",
    "closed": "3_done",
}
PROTECTED_FIELDS = {
    "campaign_id", "campaign_step", "campaign_shared", "campaign_shared_on",
    "employee_ack_date", "employee_ack_user_id",
    "manager_validated_date", "manager_validated_user_id",
}
ALIGNMENT = [("aligned", "Very aligned evaluation"), ("discuss", "Gap to discuss in the 1-on-1")]
LEVEL_MODEL = "hr.appraisal.campaign.scale.level"


class HrAppraisal(models.Model):
    _inherit = "hr.appraisal"

    campaign_id = fields.Many2one(
        "hr.appraisal.campaign", "Evaluation Campaign", index=True, ondelete="restrict",
        readonly=True)
    campaign_line_ids = fields.One2many("hr.appraisal.campaign.line", "appraisal_id", "Criteria")
    campaign_step = fields.Selection(STEPS, "Evaluation Step", tracking=True, copy=False, index=True)
    campaign_deadline = fields.Date("Step Deadline", compute="_compute_campaign_deadline", store=True)
    # set by « Meeting held — share with the employee »: before it, the employee sees
    # nothing of the manager's / final evaluation in Odoo
    campaign_shared = fields.Boolean("Meeting Held (shared with the employee)", copy=False)
    campaign_shared_on = fields.Datetime("Meeting Held On", copy=False)
    campaign_needs_evaluator = fields.Boolean(compute="_compute_campaign_needs_evaluator")
    employee_ack_date = fields.Datetime("Employee Acknowledged On", copy=False, readonly=True)
    employee_ack_user_id = fields.Many2one("res.users", "Acknowledged By", copy=False, readonly=True)
    employee_ack_comment = fields.Text("Employee Comment", copy=False)
    manager_validated_date = fields.Datetime("Manager Validated On", copy=False, readonly=True)
    manager_validated_user_id = fields.Many2one(
        "res.users", "Validated By", copy=False, readonly=True)

    # stored scores (HR / calibration only)
    score_self_total = fields.Integer("Self Total Score", compute="_compute_campaign_scores",
                                      store=True, groups=PRIVATE_GROUPS, aggregator="avg")
    score_manager_total = fields.Integer("Manager Total Score", compute="_compute_campaign_scores",
                                         store=True, groups=PRIVATE_GROUPS, aggregator="avg")
    score_final_total = fields.Integer("Final Total Score", compute="_compute_campaign_scores",
                                       store=True, groups=PRIVATE_GROUPS, aggregator="avg")
    score_gap = fields.Integer("Score Gap", compute="_compute_campaign_scores",
                               store=True, groups=PRIVATE_GROUPS)
    score_aligned = fields.Selection(
        ALIGNMENT, "Score Alignment", compute="_compute_campaign_scores", store=True,
        groups=PRIVATE_GROUPS)
    band_final_id = fields.Many2one(
        LEVEL_MODEL, "Final Overall Rating", compute="_compute_campaign_scores", store=True,
        groups=PRIVATE_GROUPS)

    # per-user view
    campaign_is_employee = fields.Boolean(compute="_compute_campaign_ui")
    campaign_is_manager = fields.Boolean(compute="_compute_campaign_ui")
    campaign_is_hr = fields.Boolean(compute="_compute_campaign_ui")
    campaign_can_see_self = fields.Boolean(compute="_compute_campaign_ui")
    campaign_can_see_manager = fields.Boolean(compute="_compute_campaign_ui")
    campaign_can_edit_self = fields.Boolean(compute="_compute_campaign_ui")
    campaign_can_edit_manager = fields.Boolean(compute="_compute_campaign_ui")
    campaign_max_total = fields.Integer("Maximum Score", compute="_compute_campaign_ui")
    ui_self_total = fields.Integer("Self-evaluation", compute="_compute_campaign_ui")
    ui_self_percent = fields.Float("Self %", compute="_compute_campaign_ui")
    ui_final_total = fields.Integer("Evaluation", compute="_compute_campaign_ui")
    ui_final_percent = fields.Float("Evaluation %", compute="_compute_campaign_ui")
    ui_band_final_id = fields.Many2one(LEVEL_MODEL, "Overall Rating", compute="_compute_campaign_ui")
    ui_gap = fields.Integer("Gap (final − self)", compute="_compute_campaign_ui")
    ui_aligned = fields.Selection(ALIGNMENT, "Alignment", compute="_compute_campaign_ui")
    ui_target_score = fields.Integer("Target", compute="_compute_campaign_ui")
    campaign_results_html = fields.Html(
        "Results", compute="_compute_campaign_ui", sanitize=False)

    # ------------------------------------------------------------------ computes
    @api.depends("campaign_step", "campaign_id.deadline_self_eval", "campaign_id.deadline_manager",
                 "campaign_id.deadline_calibration", "campaign_id.deadline_meetings")
    def _compute_campaign_deadline(self):
        for appraisal in self:
            campaign = appraisal.campaign_id
            appraisal.campaign_deadline = {
                "self_eval": campaign.deadline_self_eval,
                "manager_eval": campaign.deadline_manager,
                "calibration": campaign.deadline_calibration,
                "meeting": campaign.deadline_meetings,
                "acknowledged": campaign.deadline_meetings,
            }.get(appraisal.campaign_step) or False

    @api.depends("manager_ids")
    def _compute_campaign_needs_evaluator(self):
        for appraisal in self:
            appraisal.campaign_needs_evaluator = bool(appraisal.campaign_id) and not appraisal.manager_ids

    @staticmethod
    def _campaign_sum(lines, fname):
        grades = lines.mapped(fname)
        return sum(grades), bool(lines) and all(grades)

    def _campaign_score_values(self, lines, self_field="employee_grade", final_field="final_grade"):
        """Scores of ``lines`` (sudo'd) per section and overall:
        ``{"sections": [{section, self, final, max, self_complete, final_complete, band}],
        "total": {...same...}, "gap": int, "aligned": str|False}``."""
        self.ensure_one()
        campaign = self.campaign_id.sudo()
        Level = self.env[LEVEL_MODEL]
        top = campaign.scale_id.max_value

        def row(section, section_lines):
            s_val, s_ok = self._campaign_sum(section_lines, self_field)
            f_val, f_ok = self._campaign_sum(section_lines, final_field)
            band = campaign._campaign_band(f_val, section) if (f_ok and campaign) else Level
            return {
                "section": section, "self": s_val, "final": f_val, "max": top * len(section_lines),
                "self_complete": s_ok, "final_complete": f_ok, "band": band,
            }

        sections = []
        for section in lines.section_id.sorted(lambda s: (s.sequence, s.id)):
            sections.append(row(section, lines.filtered(lambda l, s=section: l.section_id == s)))
        total = row(self.env["hr.appraisal.campaign.section"], lines)
        res = {"sections": sections, "total": total, "gap": 0, "aligned": False}
        if total["self_complete"] and total["final_complete"]:
            res["gap"] = total["final"] - total["self"]
            res["aligned"] = "aligned" if abs(res["gap"]) <= campaign.alignment_gap else "discuss"
        return res

    @api.depends("campaign_line_ids.employee_grade", "campaign_line_ids.manager_grade",
                 "campaign_line_ids.final_grade", "campaign_line_ids.section_id",
                 "campaign_id.threshold_ids.min_score", "campaign_id.threshold_ids.level_id",
                 "campaign_id.threshold_ids.section_id", "campaign_id.alignment_gap")
    def _compute_campaign_scores(self):
        for appraisal in self:
            lines = appraisal.sudo().campaign_line_ids
            if not appraisal.campaign_id:
                appraisal.update({
                    "score_self_total": 0, "score_manager_total": 0, "score_final_total": 0,
                    "score_gap": 0, "score_aligned": False, "band_final_id": False,
                })
                continue
            res = appraisal._campaign_score_values(lines)
            appraisal.score_self_total = res["total"]["self"]
            appraisal.score_manager_total = sum(lines.mapped("manager_grade"))
            appraisal.score_final_total = res["total"]["final"]
            appraisal.score_gap = res["gap"]
            appraisal.score_aligned = res["aligned"]
            appraisal.band_final_id = res["total"]["band"]

    def _campaign_roles(self):
        """What the current user may see / do on this evaluation."""
        self.ensure_one()
        if self.env.su:
            return dict.fromkeys(
                ("hr", "manager", "see_self", "see_manager", "edit_self", "edit_manager",
                 "edit_remarks"), True,
            ) | {"employee": False}
        user = self.env.user
        appraisal = self.sudo()
        step = appraisal.campaign_step
        is_hr = user.has_group("hr_appraisal.group_hr_appraisal_user")
        is_employee = appraisal.employee_id.user_id == user
        is_manager = not is_employee and user in appraisal.manager_ids.user_id
        is_upper = not is_employee and not is_manager and bool(user.employee_ids) and bool(
            self.env["hr.employee"].sudo().search_count([
                ("id", "=", appraisal.employee_id.id),
                ("id", "child_of", user.employee_ids.ids),
            ]))
        is_calibrator = (
            not is_employee
            and user.has_group("hr_appraisal_campaign.group_campaign_calibration")
            and appraisal.campaign_id.state in ("calibration", "meetings", "closed")
        )
        reviewer = is_manager or is_upper or is_calibrator
        past_self = step not in (False, "self_eval")
        return {
            "hr": is_hr,
            "employee": is_employee,
            "manager": is_manager,
            "see_self": is_employee or is_hr or (reviewer and past_self),
            "see_manager": is_hr or reviewer or (is_employee and appraisal.campaign_shared),
            "edit_self": step == "self_eval" and (is_employee or is_hr),
            "edit_manager": step == "manager_eval" and (is_manager or is_hr),
            # remarks stay open to the evaluator (and HR) after the submission, through the
            # calibration and the meeting, until the employee acknowledges the evaluation
            "edit_remarks": (
                step in ("manager_eval", "calibration", "meeting")
                and (is_manager or is_hr) and not is_employee
                and not appraisal.employee_ack_date
            ),
        }

    def _campaign_results_data(self, roles=None):
        """Results as the current user may see them (self / final rows)."""
        self.ensure_one()
        roles = roles if roles is not None else (self._campaign_roles() if self.id else {})
        lines = self.sudo().campaign_line_ids
        res = self._campaign_score_values(lines)
        see_self = bool(roles.get("see_self"))
        see_final = bool(roles.get("see_manager")) and self.campaign_step not in (
            False, "self_eval", "manager_eval")
        if self.env.su:
            see_self = see_final = True
        res.update({
            "see_self": see_self,
            "see_final": see_final,
            "target": self.sudo().campaign_id.target_score,
        })
        return res

    @api.depends_context("uid", "lang")
    def _compute_campaign_ui(self):
        for appraisal in self:
            roles = appraisal._campaign_roles() if appraisal.id else {}
            see_self = bool(roles.get("see_self"))
            see_final = bool(roles.get("see_manager"))
            appraisal.campaign_is_employee = roles.get("employee")
            appraisal.campaign_is_manager = roles.get("manager")
            appraisal.campaign_is_hr = roles.get("hr")
            appraisal.campaign_can_see_self = see_self
            appraisal.campaign_can_see_manager = see_final
            appraisal.campaign_can_edit_self = roles.get("edit_self")
            appraisal.campaign_can_edit_manager = roles.get("edit_manager")
            if not appraisal.campaign_id:
                appraisal.update({
                    "campaign_max_total": 0, "ui_self_total": 0, "ui_self_percent": 0.0,
                    "ui_final_total": 0, "ui_final_percent": 0.0, "ui_band_final_id": False,
                    "ui_gap": 0, "ui_aligned": False, "ui_target_score": 0,
                    "campaign_results_html": False,
                })
                continue
            res = appraisal._campaign_results_data(roles)
            total = res["total"]
            maximum = total["max"] or 1
            appraisal.campaign_max_total = total["max"]
            appraisal.ui_self_total = see_self and total["self"]
            appraisal.ui_self_percent = see_self and 100.0 * total["self"] / maximum
            appraisal.ui_final_total = see_final and total["final"]
            appraisal.ui_final_percent = see_final and 100.0 * total["final"] / maximum
            appraisal.ui_band_final_id = see_final and total["band"]
            appraisal.ui_gap = (see_self and see_final) and res["gap"]
            appraisal.ui_aligned = (see_self and see_final) and res["aligned"]
            appraisal.ui_target_score = res["target"]
            appraisal.campaign_results_html = self.env["ir.qweb"]._render(
                "hr_appraisal_campaign.campaign_results_table",
                {"results": res, "appraisal": appraisal})

    # ------------------------------------------------------------------ views
    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == "form":
            # « Ask Feedback » comes from hr_appraisal_survey when it is installed (not a
            # dependency): hidden on campaign evaluations, which have their own flow.
            for button in arch.xpath("//button[@name='action_ask_feedback']"):
                invisible = button.get("invisible")
                button.set("invisible", f"({invisible}) or campaign_id" if invisible else "campaign_id")
        return arch, view

    # ------------------------------------------------------------------ ORM
    def write(self, vals):
        if not self.env.su and PROTECTED_FIELDS & set(vals) and not self.env.user.has_group(
            "hr_appraisal.group_hr_appraisal_user"
        ):
            raise AccessError(self.env._("The evaluation steps are changed with its buttons."))
        return super().write(vals)

    def send_appraisal(self):
        # campaign appraisals notify through their own to-dos
        return super(HrAppraisal, self.filtered(lambda a: not a.campaign_id)).send_appraisal()

    def _campaign_freeze_criteria(self, criteria):
        """Copy the criteria and their word pictures (all installed languages) onto each
        appraisal."""
        langs = [code for code, _name in self.env["res.lang"].get_installed()]
        base_lang = "en_US" if "en_US" in langs else langs[0]
        crit_texts = {
            lang: {c.id: c.with_context(lang=lang).read(["name", "description"])[0] for c in criteria}
            for lang in langs
        }
        pictures = criteria.level_ids
        picture_texts = {
            lang: {p.id: p.with_context(lang=lang).description for p in pictures} for lang in langs
        }
        Line = self.env["hr.appraisal.campaign.line"].sudo().with_context(lang=base_lang)
        for appraisal in self:
            vals_list = []
            for criterion in criteria:
                vals_list.append({
                    "appraisal_id": appraisal.id,
                    "criterion_id": criterion.id,
                    "section_id": criterion.section_id.id,
                    "section_sequence": criterion.section_id.sequence,
                    "sequence": criterion.sequence,
                    "name": crit_texts[base_lang][criterion.id]["name"],
                    "description": crit_texts[base_lang][criterion.id]["description"],
                    "level_text_ids": [fields.Command.create({
                        "level_id": p.level_id.id,
                        "description": picture_texts[base_lang][p.id],
                    }) for p in criterion.level_ids],
                })
            lines = Line.create(vals_list)
            for lang in langs:
                if lang == base_lang:
                    continue
                for line, criterion in zip(lines, criteria):
                    line.with_context(lang=lang).write({
                        "name": crit_texts[lang][criterion.id]["name"],
                        "description": crit_texts[lang][criterion.id]["description"],
                    })
                    for text in line.level_text_ids:
                        picture = criterion.level_ids.filtered(lambda p, t=text: p.level_id == t.level_id)
                        text.with_context(lang=lang).description = picture_texts[lang][picture.id]

    # ------------------------------------------------------------------ helpers
    def _campaign_schedule(self, users, summary_fn, deadline=False, note_fn=None):
        """To-dos; wording through the campaign's text hooks (recipient's language by default)."""
        Campaign = self.env["hr.appraisal.campaign"]
        for appraisal in self:
            for user in users:
                appraisal.sudo().activity_schedule(
                    "mail.mail_activity_data_todo",
                    deadline or fields.Date.context_today(appraisal),
                    summary=Campaign._campaign_render_text(summary_fn, user),
                    note=Campaign._campaign_render_html(note_fn, user) if note_fn else False,
                    user_id=user.id,
                )

    def _campaign_done_activities(self):
        self.sudo().activity_ids.filtered(
            lambda a: a.activity_type_id == self.env.ref("mail.mail_activity_data_todo")
        ).action_feedback()

    def _campaign_set_step(self, step):
        for appraisal in self.sudo():
            vals = {"campaign_step": step}
            target_state = ODOO_STATE_BY_STEP[step]
            if appraisal.state != target_state:
                vals["state"] = target_state
            appraisal.write(vals)

    def _campaign_check(self, condition, message):
        if not condition:
            raise UserError(message)

    # ------------------------------------------------------------------ workflow
    def _campaign_after_self_eval_steps(self):
        """Hook: action to open after the employee submits (e.g. a questionnaire)."""
        return False

    def action_campaign_submit_self(self):
        self.ensure_one()
        roles = self._campaign_roles()
        self._campaign_check(self.campaign_step == "self_eval",
                             self.env._("The self-evaluation was already submitted."))
        if not (roles["employee"] or roles["hr"]):
            raise AccessError(self.env._("Only the employee submits their self-evaluation."))
        lines = self.sudo().campaign_line_ids
        missing = lines.filtered(lambda l: not l.employee_grade)
        self._campaign_check(not missing, self.env._(
            "Grade every criterion before submitting: %s", ", ".join(missing.mapped("name"))))
        self._campaign_check(self.sudo().manager_ids, self.env._(
            "No evaluator is set on this evaluation; HR must choose one first."))
        self._campaign_done_activities()
        self._campaign_set_step("manager_eval")
        employee_name = self.sudo().employee_id.name
        self._campaign_schedule(
            self.sudo().manager_ids.user_id,
            lambda env: env._("Evaluate %s", employee_name),
            self.campaign_id.deadline_manager,
        )
        return self._campaign_after_self_eval_steps() or True

    def action_campaign_submit_manager(self):
        self.ensure_one()
        roles = self._campaign_roles()
        self._campaign_check(self.campaign_step == "manager_eval",
                             self.env._("This evaluation is not waiting for the manager."))
        if not (roles["manager"] or roles["hr"]):
            raise AccessError(self.env._("Only the evaluator submits the manager evaluation."))
        lines = self.sudo().campaign_line_ids
        missing = lines.filtered(lambda l: not l.manager_grade)
        self._campaign_check(not missing, self.env._(
            "Grade every criterion before submitting: %s", ", ".join(missing.mapped("name"))))
        for line in lines:
            line.calibrated_grade = line.manager_grade
        self._campaign_done_activities()
        self._campaign_set_step("calibration")
        if self.campaign_id.state not in ("running", "calibration"):
            self._campaign_to_meeting()
        return True

    def _campaign_to_meeting(self):
        self._campaign_set_step("meeting")
        for appraisal in self:
            employee_name = appraisal.sudo().employee_id.name
            appraisal._campaign_schedule(
                appraisal.sudo().manager_ids.user_id,
                lambda env, n=employee_name: env._("Hold the evaluation meeting with %s", n),
                appraisal.campaign_id.deadline_meetings,
            )

    def action_campaign_share(self):
        """« Meeting held — share with the employee »: the evaluator presents the
        evaluation from their own screen or printout; only once the meeting took place
        does the employee see it in Odoo (and acknowledge it)."""
        self.ensure_one()
        roles = self._campaign_roles()
        self._campaign_check(self.campaign_step == "meeting" and not self.campaign_shared, self.env._(
            "The evaluation is shared with the employee after the meeting, at the meeting step."))
        if not (roles["manager"] or roles["hr"]) or roles["employee"]:
            raise AccessError(self.env._("Only the evaluator records that the meeting was held."))
        self.sudo().write({"campaign_shared": True, "campaign_shared_on": fields.Datetime.now()})
        self.sudo().message_post(
            body=self.env["hr.appraisal.campaign"]._campaign_render_html(lambda env: env._(
                "Meeting held — the evaluation is now shared with the employee.")),
            subtype_xmlid="mail.mt_note",
            author_id=self.env.user.partner_id.id,
        )
        self._campaign_schedule(
            self.sudo().employee_id.user_id,
            lambda env: env._("Read and acknowledge your evaluation"),
            self.campaign_id.deadline_meetings,
        )
        return True

    def action_campaign_acknowledge(self):
        self.ensure_one()
        roles = self._campaign_roles()
        if not roles["employee"]:
            raise AccessError(self.env._("Only the employee acknowledges their evaluation."))
        self._campaign_check(self.campaign_step == "meeting" and self.campaign_shared,
                             self.env._("The evaluation has not been shared with you yet."))
        self.sudo().write({"employee_ack_date": fields.Datetime.now(), "employee_ack_user_id": self.env.uid})
        self.sudo().activity_ids.filtered(lambda a: a.user_id == self.env.user).action_feedback()
        self._campaign_check_acknowledged()
        return True

    def action_campaign_validate(self):
        self.ensure_one()
        roles = self._campaign_roles()
        if not (roles["manager"] or roles["hr"]) or roles["employee"]:
            raise AccessError(self.env._("Only the evaluator validates the evaluation."))
        self._campaign_check(self.campaign_step == "meeting" and self.campaign_shared,
                             self.env._("Share the evaluation with the employee first."))
        self.sudo().write({"manager_validated_date": fields.Datetime.now(),
                           "manager_validated_user_id": self.env.uid})
        self.sudo().activity_ids.filtered(lambda a: a.user_id == self.env.user).action_feedback()
        self._campaign_check_acknowledged()
        return True

    def _campaign_check_acknowledged(self):
        for appraisal in self.sudo():
            if appraisal.employee_ack_date and appraisal.manager_validated_date:
                appraisal._campaign_set_step("acknowledged")
                hr_user = appraisal.campaign_id.user_id
                if hr_user:
                    employee_name = appraisal.employee_id.name
                    appraisal._campaign_schedule(
                        hr_user, lambda env, n=employee_name: env._("Close the evaluation of %s", n))

    def action_campaign_close(self):
        if not self.env.user.has_group("hr_appraisal.group_hr_appraisal_user"):
            raise AccessError(self.env._("HR closes the evaluations."))
        for appraisal in self:
            appraisal._campaign_check(appraisal.campaign_step == "acknowledged", self.env._(
                "Both the employee and the manager must acknowledge the evaluation first."))
            appraisal._campaign_done_activities()
            appraisal._campaign_set_step("closed")
            appraisal._campaign_attach_pdf()
        return True

    def _campaign_report_lang(self):
        self.ensure_one()
        employee = self.sudo().employee_id
        return employee.user_id.lang or employee.lang or self.env.lang or "en_US"

    def _campaign_attach_pdf(self):
        report = self.env.ref("hr_appraisal_campaign.action_report_campaign_appraisal").sudo()
        for appraisal in self.sudo():
            content, fmt = report._render_qweb_pdf(
                report.report_name, appraisal.ids, data={"report_lang": appraisal._campaign_report_lang()})
            ext = "pdf" if fmt == "pdf" else "html"
            appraisal.env["ir.attachment"].create({
                "name": f"{appraisal.campaign_id.name or 'Evaluation'} - {appraisal.employee_id.name}.{ext}",
                "res_model": "hr.appraisal",
                "res_id": appraisal.id,
                "type": "binary",
                "datas": base64.b64encode(content),
                "mimetype": "application/pdf" if ext == "pdf" else "text/html",
            })

    def action_campaign_print(self):
        self.ensure_one()
        lang = self.env.context.get("report_lang") or self.env.lang
        return self.env.ref("hr_appraisal_campaign.action_report_campaign_appraisal").report_action(
            self, data={"report_lang": lang})
