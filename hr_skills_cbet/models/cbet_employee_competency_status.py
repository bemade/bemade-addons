from odoo import fields, models
from odoo.tools import SQL


class CbetEmployeeCompetencyStatus(models.Model):
    """UC-RPT-04 — the employees × competencies training matrix.

    A SQL view (_auto=False, AC3) over the tracked (employee, competency) pairs
    — those appearing in a certification or a training line — computing the
    per-cell state. Certification-less pairs surface as 'none'. Feeds the
    coverage-% pivot and the decoration-coloured RAG list.
    """

    _name = "cbet.employee.competency.status"
    _description = "CBET Employee × Competency Status"
    _auto = False
    _order = "employee_id, competency_id"

    employee_id = fields.Many2one("hr.employee", readonly=True)
    competency_id = fields.Many2one("cbet.competency", readonly=True)
    domain_id = fields.Many2one("cbet.domain", readonly=True)
    certification_id = fields.Many2one("cbet.certification", readonly=True)
    valid_to = fields.Date(readonly=True)
    state = fields.Selection(
        [
            ("none", "None"),
            ("valid", "Valid"),
            ("expiring", "Expiring"),
            ("expired", "Expired"),
        ],
        readonly=True,
    )

    def init(self):
        # Default 3-month expiry horizon baked into the view (UC-VAL-01 AC1 default).
        self.env.cr.execute(SQL("DROP VIEW IF EXISTS %s", SQL.identifier(self._table)))
        self.env.cr.execute(SQL(
            """
            CREATE VIEW %(table)s AS
            WITH pairs AS (
                SELECT employee_id, competency_id FROM cbet_certification
                UNION
                SELECT employee_id, competency_id FROM cbet_training_line
            ),
            latest AS (
                SELECT DISTINCT ON (employee_id, competency_id)
                       id, employee_id, competency_id, valid_to
                FROM cbet_certification
                WHERE active = TRUE
                ORDER BY employee_id, competency_id, valid_from DESC
            )
            SELECT row_number() OVER () AS id,
                   p.employee_id,
                   p.competency_id,
                   c.domain_id,
                   l.id AS certification_id,
                   l.valid_to,
                   CASE
                       WHEN l.id IS NULL THEN 'none'
                       WHEN l.valid_to IS NOT NULL AND l.valid_to < CURRENT_DATE THEN 'expired'
                       WHEN l.valid_to IS NOT NULL
                            AND l.valid_to <= CURRENT_DATE + INTERVAL '3 months' THEN 'expiring'
                       ELSE 'valid'
                   END AS state
            FROM pairs p
            JOIN cbet_competency c ON c.id = p.competency_id
            LEFT JOIN latest l
                   ON l.employee_id = p.employee_id
                  AND l.competency_id = p.competency_id
            """,
            table=SQL.identifier(self._table),
        ))
