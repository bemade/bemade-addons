from odoo import fields, models


class CbetEvaluationSession(models.Model):
    """UC-EVL-01 — a session bundling one or more competency-unit evaluations
    for one candidate."""

    _name = "cbet.evaluation.session"
    _description = "CBET Evaluation Session"
    _order = "date desc, id desc"

    name = fields.Char(required=True, default="New session")
    date = fields.Date(default=fields.Date.context_today)
    place = fields.Char()
    candidate_id = fields.Many2one("hr.employee", string="Candidate")
    evaluator_id = fields.Many2one("res.users", string="Evaluator",
                                   default=lambda self: self.env.user)
    evaluation_ids = fields.One2many("cbet.evaluation", "session_id")
    evaluation_count = fields.Integer(compute="_compute_evaluation_count")

    def _compute_evaluation_count(self):
        for session in self:
            session.evaluation_count = len(session.evaluation_ids)
