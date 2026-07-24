from odoo import fields, models


class CbetEvaluationUnit(models.Model):
    """UC-CAT-06 — 1..n evaluation units per competency (D6). Certification
    requires all *required* units passed (UC-EVL-09)."""

    _name = "cbet.evaluation.unit"
    _description = "CBET Evaluation Unit"
    _order = "competency_id, sequence, id"

    competency_id = fields.Many2one(
        "cbet.competency", required=True, ondelete="cascade", index=True,
    )
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    required = fields.Boolean(default=True)
    is_default = fields.Boolean(
        help="The auto-created default unit for single-unit competencies.",
    )
    criterion_ids = fields.One2many("cbet.criterion", "unit_id", copy=True)
    protocol_notes = fields.Html(
        translate=True, help="Optional protocol override for this unit (UC-CAT-06 AC2).",
    )
