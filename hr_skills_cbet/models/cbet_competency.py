import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

CODE_RE = re.compile(r"^[A-Za-z]{2,4}-\d{1,3}$")


class CbetCompetency(models.Model):
    """UC-CAT-02 — a coded competency node (XXX-NN), not an hr.skill (D1)."""

    _name = "cbet.competency"
    _description = "CBET Competency"
    _order = "domain_id, code"
    _inherit = ["mail.thread"]

    code = fields.Char(required=True, tracking=True)
    name = fields.Char(required=True, translate=True, tracking=True)
    domain_id = fields.Many2one("cbet.domain", string="Domain", tracking=True)
    kind = fields.Selection(
        [
            ("procedural", "Procedural"),
            ("theoretical", "Theoretical"),
            ("orchestration", "Orchestration"),
        ],
        required=True,
        default="procedural",
        tracking=True,
        help="Theoretical competencies have no Part A (practical) requirement.",
    )
    active = fields.Boolean(default=True)

    # Lifecycle (UC-CAT-09).
    state = fields.Selection(
        [("draft", "Draft"), ("published", "Published")],
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )
    version = fields.Char(default="0.1", copy=False, tracking=True)
    publish_date = fields.Date(copy=False, readonly=True)
    version_ids = fields.One2many("cbet.competency.version", "competency_id")

    # Catalog content (UC-CAT-02 AC3).
    execution_context = fields.Html(translate=True)
    safety_block = fields.Html(translate=True)
    tools_materials = fields.Html(translate=True)
    # Trainer metadata.
    field_frequency = fields.Char()
    difficulty = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
    )
    learning_time = fields.Char()
    common_pitfalls = fields.Text()

    # Children.
    unit_ids = fields.One2many("cbet.evaluation.unit", "competency_id", copy=True)
    question_ids = fields.One2many("cbet.question", "competency_id", copy=True)
    prerequisite_ids = fields.One2many(
        "cbet.prerequisite", "competency_id", string="Prerequisites", copy=True,
    )
    criterion_ids = fields.One2many(
        "cbet.criterion", "competency_id", string="All criteria (via units)",
    )

    # Evaluation policy (UC-CAT-04, UC-CAT-07).
    pass_threshold = fields.Float(
        string="Overall pass threshold (%)",
        default=80.0,
        help="Ratio of réussi over ALL applicable criteria (sec+crit+standard, "
             "s.o. excluded). Security & critical criteria are a separate hard gate.",
    )
    validity_months = fields.Integer(
        string="Certification validity (months)",
        default=lambda self: self.env.company.cbet_default_validity_months,
    )
    reprise_deadline_days = fields.Integer(
        string="Reprise deadline (days)",
        default=lambda self: self.env.company.cbet_reprise_deadline_days,
    )
    # Evaluation protocol (UC-CAT-07).
    protocol_method = fields.Char()
    protocol_place = fields.Char()
    protocol_duration = fields.Float(string="Protocol duration (hours)")
    protocol_support = fields.Char(string="Allowed support")
    protocol_min_evaluator_qualification = fields.Char(
        help="PLAN §5 policy value — designated trainer vs Classe II, per competency.",
    )
    designated_trainer_ids = fields.Many2many(
        "res.users",
        string="Designated trainers",
        help="UC-EVL-02 AC1: only these users may evaluate this competency "
             "(CBET Evaluator group necessary but not sufficient).",
    )

    @api.constrains("code")
    def _check_code(self):
        for comp in self:
            if not comp.code or not CODE_RE.match(comp.code):
                raise ValidationError(
                    self.env._("Competency code %s must match XXX-NN "
                               "(2–4 letters, dash, 1–3 digits).", comp.code or ""))
            # Case-insensitive uniqueness.
            dup = self.search_count([
                ("id", "!=", comp.id),
                ("code", "=ilike", comp.code),
            ])
            if dup:
                raise ValidationError(
                    self.env._("A competency with code %s already exists "
                               "(codes are case-insensitive).", comp.code))

    @api.model_create_multi
    def create(self, vals_list):
        comps = super().create(vals_list)
        # UC-CAT-06 AC1: every competency has ≥1 unit (default unit auto-created).
        for comp in comps:
            if not comp.unit_ids:
                self.env["cbet.evaluation.unit"].create({
                    "competency_id": comp.id,
                    "name": self.env._("Default unit"),
                    "required": True,
                    "is_default": True,
                })
        return comps

    # ------------------------------------------------------------------
    # UC-CAT-03 AC4 — transitive obligatory closure.
    # ------------------------------------------------------------------
    def _obligatory_closure(self):
        """Return self plus every competency reachable through *obligatoire*
        prerequisite edges (transitive)."""
        result = self.browse()
        todo = self
        while todo:
            result |= todo
            nxt = todo.mapped("prerequisite_ids").filtered(
                lambda e: e.prereq_type == "obligatoire",
            ).mapped("prerequisite_id")
            todo = nxt - result
        return result

    # ------------------------------------------------------------------
    # UC-CAT-09 — publication workflow (Manager only).
    # ------------------------------------------------------------------
    def _bump_version(self):
        self.ensure_one()
        # First publication lands on 1.0; subsequent publications bump the minor.
        if not self.version_ids:
            return "1.0"
        try:
            major, minor = self.version.split(".")
            return "%s.%s" % (major, int(minor) + 1)
        except (ValueError, AttributeError):
            return "1.0"

    def action_publish(self):
        if not self.env.user.has_group("hr_skills_cbet.group_cbet_manager"):
            raise UserError(self.env._("Only a CBET Manager can publish competencies."))
        for comp in self:
            comp.version = comp._bump_version()
            comp.publish_date = fields.Date.context_today(comp)
            comp.state = "published"
            self.env["cbet.competency.version"]._snapshot(comp)
        return True

    def action_reset_to_draft(self):
        if not self.env.user.has_group("hr_skills_cbet.group_cbet_manager"):
            raise UserError(self.env._("Only a CBET Manager can change competency state."))
        self.state = "draft"
        return True
