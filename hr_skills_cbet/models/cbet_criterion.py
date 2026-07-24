from odoo import fields, models


class CbetCriterion(models.Model):
    """UC-CAT-04 — a sequenced, typed performance criterion on an evaluation unit."""

    _name = "cbet.criterion"
    _description = "CBET Performance Criterion"
    _order = "unit_id, sequence, id"

    unit_id = fields.Many2one(
        "cbet.evaluation.unit", required=True, ondelete="cascade", index=True,
    )
    competency_id = fields.Many2one(
        "cbet.competency", related="unit_id.competency_id", store=True, index=True,
    )
    sequence = fields.Integer(default=10)
    criterion_type = fields.Selection(
        [
            ("security", "Security 🔒"),
            ("critical", "Critical ⚠️"),
            ("standard", "Standard ▫️"),
        ],
        required=True,
        default="standard",
    )
    text = fields.Text(required=True, translate=True)
    verification_method = fields.Char(translate=True)
    tolerance = fields.Char(translate=True)
