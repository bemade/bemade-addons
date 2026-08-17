from odoo import fields, models
from odoo.tools import SQL


class CbetEmployeeCompetencyStatus(models.Model):
    """UC-RPT-04 — the employees × competencies training matrix.

    A SQL view (_auto=False, AC3) computing the per-cell state. The rows are
    every (employee, competency) pair that is either *required* — the obligatory
    closure of the standards the employee is qualifying against, mirroring
    ``cbet.competency._obligatory_closure`` — or already *tracked*, through a
    certification or a training line.

    Requirements are what make this a training matrix rather than a list of
    holdings: a competency the employee owes but has never been certified on
    surfaces as a 'none' cell (AC2), and ``is_required`` separates those gaps
    from competencies held over and above the standard. Feeds the coverage-%
    pivot and the decoration-coloured RAG list.
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
    is_required = fields.Boolean(
        string="Required", readonly=True,
        help="The competency belongs to the obligatory closure of a standard "
             "this employee is qualifying against.",
    )
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
            WITH RECURSIVE closure AS (
                -- Seed: the competencies each standard names as essential.
                SELECT sl.standard_id, sl.competency_id
                FROM cbet_standard_line sl
                WHERE sl.line_type = 'essential'
                UNION
                -- Transitively pull in obligatory prerequisites. UNION (not
                -- UNION ALL) both de-duplicates and terminates on cycles.
                SELECT cl.standard_id, p.prerequisite_id
                FROM closure cl
                JOIN cbet_prerequisite p ON p.competency_id = cl.competency_id
                WHERE p.prereq_type = 'obligatoire'
            ),
            required AS (
                SELECT DISTINCT q.employee_id, cl.competency_id
                FROM cbet_qualification q
                JOIN cbet_standard s ON s.id = q.standard_id AND s.active = TRUE
                JOIN closure cl ON cl.standard_id = q.standard_id
            ),
            pairs AS (
                SELECT employee_id, competency_id FROM required
                UNION
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
                   (r.employee_id IS NOT NULL) AS is_required,
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
            LEFT JOIN required r
                   ON r.employee_id = p.employee_id
                  AND r.competency_id = p.competency_id
            """,
            table=SQL.identifier(self._table),
        ))
