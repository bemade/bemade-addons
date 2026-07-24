from odoo import fields, models


class CbetTrainingLine(models.Model):
    """UC-TRN-02 AC3 (MVP sliver) — the durable per-(employee, competency)
    'trainer of record'. The full TWI pipeline (statuses, kanban, timesheet-
    backed session notes) hangs off this same record at P2."""

    _name = "cbet.training.line"
    _description = "CBET Training Line (trainer of record)"
    _order = "employee_id, competency_id"

    employee_id = fields.Many2one(
        "hr.employee", required=True, ondelete="cascade", index=True,
    )
    competency_id = fields.Many2one(
        "cbet.competency", required=True, ondelete="cascade", index=True,
    )
    trainer_id = fields.Many2one(
        "res.users", string="Trainer of record",
        help="UC-EVL-02 AC2: the evaluator may not be this trainer (TWI independence).",
    )

    _emp_comp_uniq = models.Constraint(
        "unique(employee_id, competency_id)",
        "A training line already exists for this employee and competency.",
    )
