from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class CbetEvaluation(models.Model):
    """UC-EVL-01..10 — a signed practical + oral evaluation of one competency
    unit for one candidate."""

    _name = "cbet.evaluation"
    _description = "CBET Evaluation"
    _order = "date desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(default="New evaluation", copy=False)
    session_id = fields.Many2one("cbet.evaluation.session", ondelete="set null")
    competency_id = fields.Many2one(
        "cbet.competency", required=True, ondelete="restrict", index=True)
    unit_id = fields.Many2one(
        "cbet.evaluation.unit", required=True, ondelete="restrict",
        domain="[('competency_id', '=', competency_id)]")
    competency_version_id = fields.Many2one("cbet.competency.version", copy=False)
    candidate_id = fields.Many2one("hr.employee", required=True, ondelete="restrict")
    evaluator_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.user)
    date = fields.Date(default=fields.Date.context_today)
    place = fields.Char()
    equipment_model = fields.Char()
    equipment_serial = fields.Char()

    criterion_result_ids = fields.One2many(
        "cbet.criterion.result", "evaluation_id", copy=True)
    question_result_ids = fields.One2many(
        "cbet.question.result", "evaluation_id", copy=True)

    state = fields.Selection(
        [("draft", "Draft"), ("in_progress", "In progress"),
         ("completed", "Completed")],
        default="draft", required=True, copy=False, tracking=True)
    locked = fields.Boolean(copy=False)
    active = fields.Boolean(default=True)

    # Decision (UC-EVL-05).
    security_critical_ok = fields.Boolean(compute="_compute_indicators")
    overall_ratio = fields.Float(compute="_compute_indicators", string="Overall %")
    standard_pass = fields.Boolean(compute="_compute_indicators")
    essential_questions_ok = fields.Boolean(compute="_compute_indicators")
    computed_pass = fields.Boolean(compute="_compute_indicators")
    suggested_decision = fields.Selection(
        [("reussi", "Passed"), ("reprise_ciblee", "Targeted retake"), ("echec", "Failed")],
        compute="_compute_indicators")
    decision = fields.Selection(
        [("reussi", "Passed"), ("reprise_ciblee", "Targeted retake"), ("echec", "Failed")],
        copy=False, tracking=True)
    evaluator_comments = fields.Text()

    # Signatures (UC-EVL-07, D4).
    evaluator_signature = fields.Binary(copy=False)
    candidate_signature = fields.Binary(copy=False)
    evaluator_signed_date = fields.Datetime(copy=False)
    candidate_signed_date = fields.Datetime(copy=False)

    # Targeted retake — 'reprise ciblée' in the source plan (UC-EVL-06).
    reprise_parent_id = fields.Many2one(
        "cbet.evaluation", string="Retake of", copy=False)
    reprise_child_ids = fields.One2many(
        "cbet.evaluation", "reprise_parent_id", string="Retakes")
    is_reprise = fields.Boolean(
        string="Is a retake", compute="_compute_is_reprise", store=True)
    reprise_deadline = fields.Date(string="Retake deadline", copy=False)

    # ------------------------------------------------------------------
    @api.depends("reprise_parent_id")
    def _compute_is_reprise(self):
        for ev in self:
            ev.is_reprise = bool(ev.reprise_parent_id)

    @api.depends("criterion_result_ids.result", "criterion_result_ids.criterion_type",
                 "question_result_ids.result", "question_result_ids.essential",
                 "competency_id.pass_threshold")
    def _compute_indicators(self):
        for ev in self:
            crits = ev.criterion_result_ids
            sec_crit = crits.filtered(lambda c: c.criterion_type in ("security", "critical"))
            ev.security_critical_ok = not any(c.result == "echec" for c in sec_crit)
            applicable = crits.filtered(lambda c: c.result in ("reussi", "echec"))
            passed = applicable.filtered(lambda c: c.result == "reussi")
            ev.overall_ratio = (100.0 * len(passed) / len(applicable)) if applicable else 100.0
            ev.standard_pass = ev.overall_ratio >= (ev.competency_id.pass_threshold or 0.0)
            essential_q = ev.question_result_ids.filtered("essential")
            ev.essential_questions_ok = all(q.result == "acquis" for q in essential_q)
            ev.computed_pass = (
                ev.security_critical_ok and ev.standard_pass and ev.essential_questions_ok)
            ev.suggested_decision = "reussi" if ev.computed_pass else "reprise_ciblee"

    # ------------------------------------------------------------------
    # UC-EVL-02 — evaluator constraints.
    # ------------------------------------------------------------------
    @api.constrains("evaluator_id", "candidate_id", "competency_id")
    def _check_evaluator(self):
        for ev in self:
            if self.env.context.get("cbet_override_independence"):
                continue
            comp = ev.competency_id
            # AC1 — designated trainer for this specific competency.
            if comp.designated_trainer_ids and ev.evaluator_id not in comp.designated_trainer_ids:
                raise ValidationError(self.env._(
                    "%(user)s is not a designated trainer for competency %(code)s.",
                    user=ev.evaluator_id.name, code=comp.code))
            # AC2 — evaluator ≠ candidate.
            if ev.candidate_id.user_id and ev.candidate_id.user_id == ev.evaluator_id:
                raise ValidationError(self.env._(
                    "The evaluator cannot be the candidate."))
            # AC2 — evaluator ≠ candidate's direct trainer of record.
            line = self.env["cbet.training.line"].search([
                ("employee_id", "=", ev.candidate_id.id),
                ("competency_id", "=", comp.id),
            ], limit=1)
            if line.trainer_id and line.trainer_id == ev.evaluator_id:
                raise ValidationError(self.env._(
                    "TWI independence: the evaluator is the candidate's direct "
                    "trainer for %(code)s. A Manager override is required.",
                    code=comp.code))

    @api.constrains("decision", "criterion_result_ids")
    def _check_decision_hard_gate(self):
        for ev in self:
            # UC-EVL-05 AC3 — cannot record a pass over a failed security/critical.
            if ev.decision == "reussi" and not ev.security_critical_ok:
                raise ValidationError(self.env._(
                    "Cannot record a pass: a security or critical criterion has failed."))

    # ------------------------------------------------------------------
    # UC-EVL-03/04 — open the evaluation, snapshot criteria & questions.
    # ------------------------------------------------------------------
    def action_start(self):
        for ev in self:
            comp = ev.competency_id
            # UC-CAT-09 AC2 — only published competencies can be evaluated.
            if comp.state != "published":
                raise UserError(self.env._(
                    "Competency %s is not published; it cannot be evaluated.", comp.code))
            version = comp.version_ids[:1]
            ev.competency_version_id = version
            ev.criterion_result_ids.unlink()
            ev.question_result_ids.unlink()
            criteria, questions = ev._grid_from_version(version)
            ev.criterion_result_ids = criteria
            ev.question_result_ids = questions
            ev.state = "in_progress"
        return True

    def _grid_from_version(self, version):
        """Build the Part A / Part B lines from the *pinned* published version.

        The evaluation records which version it was run against, so the grid has
        to come from that version's frozen snapshot rather than from the live
        catalogue: the live rows can have been replaced since (a markdown
        re-import swaps them wholesale), and an evaluation stamped v1.0 must
        never contain criteria that v1.0 never had.
        """
        self.ensure_one()
        snapshot = version.snapshot or {}
        if not snapshot:
            # Nothing frozen (published before snapshots existed): fall back to
            # the live catalogue rather than produce an empty grid.
            return self._grid_from_catalog()

        kind = snapshot.get("kind") or self.competency_id.kind
        units = snapshot.get("units") or []
        unit = next((u for u in units if u.get("id") == self.unit_id.id), None)
        if unit is None and len(units) == 1:
            unit = units[0]
        if unit is None:
            unit = next((u for u in units if u.get("name") == self.unit_id.name), {})

        criteria = []
        # UC-EVL-03 AC3 — theoretical competencies produce no Part A lines.
        if kind != "theoretical":
            rows = unit.get("criteria") or []
            alive = self._alive_snapshot_ids("cbet.criterion", rows)
            criteria = [
                (0, 0, {
                    "source_criterion_id": c["id"] if c.get("id") in alive else False,
                    "sequence": c.get("sequence") or (i + 1) * 10,
                    "criterion_type": c["type"],
                    "text": c["text"],
                    "verification_method": c.get("verification_method"),
                    "tolerance": c.get("tolerance"),
                })
                for i, c in enumerate(rows)
            ]

        q_rows = snapshot.get("questions") or []
        alive_q = self._alive_snapshot_ids("cbet.question", q_rows)
        questions = [
            (0, 0, {
                "source_question_id": q["id"] if q.get("id") in alive_q else False,
                "sequence": q.get("sequence") or (i + 1) * 10,
                "text": q["text"],
                "expected_answer": q.get("expected_answer"),
                "essential": q.get("essential", False),
            })
            for i, q in enumerate(q_rows)
        ]
        return criteria, questions

    def _alive_snapshot_ids(self, model, rows):
        """Which snapshot row ids still exist — the catalogue rows they were
        taken from may since have been deleted and replaced."""
        ids = [r["id"] for r in rows if r.get("id")]
        return set(self.env[model].browse(ids).exists().ids) if ids else set()

    def _grid_from_catalog(self):
        """Legacy path — build the grid from the live catalogue rows."""
        self.ensure_one()
        criteria = []
        if self.competency_id.kind != "theoretical":
            criteria = [
                (0, 0, {
                    "source_criterion_id": c.id,
                    "sequence": c.sequence,
                    "criterion_type": c.criterion_type,
                    "text": c.text,
                    "verification_method": c.verification_method,
                    "tolerance": c.tolerance,
                })
                for c in self.unit_id.criterion_ids
            ]
        questions = [
            (0, 0, {
                "source_question_id": q.id,
                "sequence": q.sequence,
                "text": q.text,
                "expected_answer": q.expected_answer,
                "essential": q.essential,
            })
            for q in self.competency_id.question_ids
        ]
        return criteria, questions

    # ------------------------------------------------------------------
    # UC-EVL-07 — signatures & completion/locking.
    # ------------------------------------------------------------------
    def _sign(self, field):
        self.ensure_one()
        self[field] = b"stub-signature"  # tests set real data; UI uses signature widget
        self[field.replace("_signature", "_signed_date")] = fields.Datetime.now()

    def action_complete(self):
        for ev in self:
            if not ev.decision:
                raise UserError(self.env._("Set a decision before completing."))
            if not (ev.evaluator_signature and ev.candidate_signature):
                raise UserError(self.env._(
                    "Both evaluator and candidate signatures are required."))
            if ev.decision == "reprise_ciblee":
                ev._create_reprise()
            ev.state = "completed"
            ev.locked = True
            if ev.decision == "reussi":
                ev._maybe_issue_certification()
        return True

    def action_unlock(self, reason=None):
        if not self.env.user.has_group("hr_skills_cbet.group_cbet_manager"):
            raise UserError(self.env._("Only a CBET Manager can unlock an evaluation."))
        for ev in self:
            ev.message_post(body=self.env._("Evaluation unlocked. Reason: %s", reason or "—"))
            ev.locked = False
        return True

    # Fields still writable on a locked record: the lock toggle, archiving
    # (retention = archive only, UC-EVL-08 AC2), and chatter plumbing.
    _LOCKED_WRITABLE = {"locked", "active", "message_main_attachment_id"}

    def write(self, vals):
        # UC-EVL-07 AC2 — locked records are immutable except the fields above.
        if any(ev.locked for ev in self) and set(vals) - self._LOCKED_WRITABLE:
            raise UserError(self.env._(
                "This evaluation is locked. A CBET Manager must unlock it first."))
        # UC-EVL-07 AC1 — stamp when each party signed. The form's signature
        # widget writes the image straight to the field, so the date has to be
        # derived here rather than in a dedicated action.
        for sig in ("evaluator_signature", "candidate_signature"):
            if sig not in vals:
                continue
            stamp = sig.replace("_signature", "_signed_date")
            if stamp in vals:
                continue
            vals[stamp] = fields.Datetime.now() if vals[sig] else False
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_block_completed(self):
        # UC-EVL-08 AC2 — completed evaluations cannot be deleted (archive only).
        if any(ev.state == "completed" for ev in self):
            raise UserError(self.env._(
                "Completed evaluations cannot be deleted (retention). Archive instead."))

    # ------------------------------------------------------------------
    # UC-EVL-06 — reprise ciblée follow-up.
    # ------------------------------------------------------------------
    def _create_reprise(self):
        self.ensure_one()
        # AC3 — a reprise cannot itself spawn a reprise (single retry).
        if self.is_reprise:
            raise UserError(self.env._(
                "A targeted retake cannot spawn another retake; a full "
                "re-evaluation is required."))
        failed_crits = self.criterion_result_ids.filtered(
            lambda c: c.result == "echec" and c.criterion_type in ("security", "critical"))
        failed_questions = self.question_result_ids.filtered(
            lambda q: q.essential and q.result == "a_revoir")
        deadline_days = self.competency_id.reprise_deadline_days or 30
        reprise = self.create({
            "name": self.env._("Retake — %s", self.name),
            "competency_id": self.competency_id.id,
            "unit_id": self.unit_id.id,
            "candidate_id": self.candidate_id.id,
            "evaluator_id": self.evaluator_id.id,
            "competency_version_id": self.competency_version_id.id,
            "reprise_parent_id": self.id,
            "reprise_deadline": fields.Date.context_today(self) + relativedelta(days=deadline_days),
            "state": "in_progress",
            "criterion_result_ids": [
                (0, 0, {
                    "source_criterion_id": c.source_criterion_id.id,
                    "sequence": c.sequence, "criterion_type": c.criterion_type,
                    "text": c.text, "verification_method": c.verification_method,
                    "tolerance": c.tolerance, "is_retake": True,
                })
                for c in failed_crits
            ],
            "question_result_ids": [
                (0, 0, {
                    "source_question_id": q.source_question_id.id,
                    "sequence": q.sequence, "text": q.text,
                    "expected_answer": q.expected_answer, "essential": q.essential,
                    "is_retake": True,
                })
                for q in failed_questions
            ],
        })
        return reprise

    # ------------------------------------------------------------------
    # UC-EVL-09/10 — multi-unit assembly & certification issuance.
    # ------------------------------------------------------------------
    def _passing_unit_evaluations(self):
        """Completed, passed evaluations for this candidate & competency, one per
        required unit."""
        self.ensure_one()
        return self.search([
            ("candidate_id", "=", self.candidate_id.id),
            ("competency_id", "=", self.competency_id.id),
            ("state", "=", "completed"),
            ("decision", "=", "reussi"),
        ])

    def _maybe_issue_certification(self):
        self.ensure_one()
        comp = self.competency_id
        required_units = comp.unit_ids.filtered("required")
        passes = self._passing_unit_evaluations()
        passed_units = passes.mapped("unit_id")
        if not (required_units and required_units <= passed_units):
            return False  # not all required units passed yet (UC-EVL-09 AC1)
        valid_from = max(passes.mapped("date"))
        validity = comp.validity_months or self.env.company.cbet_default_validity_months
        valid_to = valid_from + relativedelta(months=validity)
        # Supersede any prior active certification (versioned-row, UC-EVL-10 AC2).
        prior = self.env["cbet.certification"].search([
            ("employee_id", "=", self.candidate_id.id),
            ("competency_id", "=", comp.id),
            ("active", "=", True),
        ])
        prior.active = False
        cert = self.env["cbet.certification"].create({
            "employee_id": self.candidate_id.id,
            "competency_id": comp.id,
            "competency_version_id": self.competency_version_id.id,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "source_evaluation_ids": [(6, 0, passes.ids)],
        })
        # UC-EVL-10 AC3 — issuance triggers qualification recompute.
        self.env["cbet.qualification"]._recompute_for_employee(self.candidate_id, comp)
        return cert
