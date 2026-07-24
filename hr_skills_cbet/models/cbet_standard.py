from odoo import api, fields, models


class CbetStandard(models.Model):
    """UC-STD-01 — a qualification standard (Classe I, I-B, …)."""

    _name = "cbet.standard"
    _description = "CBET Qualification Standard"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    role_description = fields.Text(translate=True)
    active = fields.Boolean(default=True)

    line_ids = fields.One2many("cbet.standard.line", "standard_id", copy=True)
    essential_competency_ids = fields.Many2many(
        "cbet.competency", compute="_compute_sets", string="Essential competencies",
    )
    closed_competency_ids = fields.Many2many(
        "cbet.competency", compute="_compute_sets", string="Full requirement set",
        help="UC-STD-01 AC2 — transitive obligatory closure over the essentials.",
    )
    pulled_in_competency_ids = fields.Many2many(
        "cbet.competency", compute="_compute_sets",
        string="Pulled in by prerequisite",
    )
    required_count = fields.Integer(compute="_compute_sets")

    # UC-STD-03 — tie-back to a coarse hr.skill certification.
    skill_id = fields.Many2one(
        "hr.skill", string="Tie-back certification skill", ondelete="restrict",
        help="hr.skill (is_certification) granted when the qualification is achieved.",
    )

    # UC-STD-04 — sub-qualifications.
    parent_standard_id = fields.Many2one("cbet.standard", string="Extension of")
    is_sub_qualification = fields.Boolean(
        compute="_compute_is_sub", store=True,
    )

    qualification_ids = fields.One2many("cbet.qualification", "standard_id")

    @api.depends("parent_standard_id")
    def _compute_is_sub(self):
        for std in self:
            std.is_sub_qualification = bool(std.parent_standard_id)

    @api.depends("line_ids.line_type", "line_ids.competency_id",
                 "line_ids.competency_id.prerequisite_ids.prereq_type",
                 "line_ids.competency_id.prerequisite_ids.prerequisite_id")
    def _compute_sets(self):
        for std in self:
            essentials = std.line_ids.filtered(
                lambda l: l.line_type == "essential").mapped("competency_id")
            closure = essentials._obligatory_closure() if essentials else essentials
            std.essential_competency_ids = essentials
            std.closed_competency_ids = closure
            std.pulled_in_competency_ids = closure - essentials
            std.required_count = len(closure)
