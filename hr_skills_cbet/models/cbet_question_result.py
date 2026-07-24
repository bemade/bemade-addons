from odoo import fields, models


class CbetQuestionResult(models.Model):
    """UC-EVL-04 — a Part B question result line, snapshotted like Part A."""

    _name = "cbet.question.result"
    _description = "CBET Question Result (Part B)"
    _order = "evaluation_id, sequence, id"

    evaluation_id = fields.Many2one(
        "cbet.evaluation", required=True, ondelete="cascade", index=True,
    )
    source_question_id = fields.Many2one("cbet.question", ondelete="set null")
    sequence = fields.Integer(default=10)
    # Frozen snapshot.
    text = fields.Text(required=True)
    expected_answer = fields.Text()
    essential = fields.Boolean()

    result = fields.Selection(
        [("acquis", "Acquis"), ("a_revoir", "À revoir")],
        default="a_revoir",
        required=True,
    )
    is_retake = fields.Boolean()
