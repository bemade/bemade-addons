from odoo import fields, models


class CbetStandardLine(models.Model):
    """A competency line on a qualification standard (UC-STD-01)."""

    _name = "cbet.standard.line"
    _description = "CBET Standard Competency Line"

    standard_id = fields.Many2one(
        "cbet.standard", required=True, ondelete="cascade", index=True,
    )
    competency_id = fields.Many2one(
        "cbet.competency", required=True, ondelete="restrict",
    )
    line_type = fields.Selection(
        [("essential", "Essential"), ("optional", "Optional")],
        required=True,
        default="essential",
    )

    _line_uniq = models.Constraint(
        "unique(standard_id, competency_id)",
        "A competency can appear only once on a standard.",
    )
