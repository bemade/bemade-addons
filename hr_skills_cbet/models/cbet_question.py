from odoo import fields, models


class CbetQuestion(models.Model):
    """UC-CAT-05 — Part B oral knowledge question. Shared per competency (one
    Part B bank across all units/annexes)."""

    _name = "cbet.question"
    _description = "CBET Knowledge Question (Part B)"
    _order = "competency_id, sequence, id"

    competency_id = fields.Many2one(
        "cbet.competency", required=True, ondelete="cascade", index=True,
    )
    sequence = fields.Integer(default=10)
    text = fields.Text(required=True, translate=True)
    expected_answer = fields.Text(translate=True)
    section_ref = fields.Char(string="Fiche section reference")
    essential = fields.Boolean(
        help="Essential questions must be answered correctly for the "
             "evaluation to pass.",
    )
