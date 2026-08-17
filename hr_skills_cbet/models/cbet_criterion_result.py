from odoo import fields, models


class CbetCriterionResult(models.Model):
    """UC-EVL-03 — a Part A criterion result line, snapshotted from the
    published criterion at evaluation-open time (text/type/method/tolerance
    frozen on the record)."""

    _name = "cbet.criterion.result"
    _description = "CBET Criterion Result (Part A)"
    _order = "evaluation_id, sequence, id"

    evaluation_id = fields.Many2one(
        "cbet.evaluation", required=True, ondelete="cascade", index=True,
    )
    source_criterion_id = fields.Many2one("cbet.criterion", ondelete="set null")
    sequence = fields.Integer(default=10)
    # Frozen snapshot.
    criterion_type = fields.Selection(
        [("security", "Security 🔒"), ("critical", "Critical ⚠️"), ("standard", "Standard ▫️")],
        required=True,
    )
    text = fields.Text(required=True)
    verification_method = fields.Char()
    tolerance = fields.Char()

    result = fields.Selection(
        [("reussi", "Passed"), ("echec", "Failed"), ("so", "N/A")],
        default="so",
        required=True,
    )
    is_retake = fields.Boolean(help="Included in a targeted-retake set.")
