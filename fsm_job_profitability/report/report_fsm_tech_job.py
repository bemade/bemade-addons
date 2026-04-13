from odoo import fields, models, tools


class ReportFsmTechJob(models.Model):
    """Technician-level FSM job profitability.

    Grain: one row per (sale order, technician). Revenue is the job-level FSM
    revenue allocated to each technician in proportion to their share of
    effective hours on that job.
    """

    _name = "report.fsm.tech.job"
    _description = "FSM Technician Job Profitability"
    _auto = False

    sale_order_id = fields.Many2one("sale.order", string="Sales Order", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Customer", readonly=True)
    date_order = fields.Datetime(string="Order Date", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", readonly=True)

    user_id = fields.Many2one("res.users", string="Technician (User)", readonly=True)
    employee_id = fields.Many2one(
        "hr.employee", string="Technician (Employee)", readonly=True
    )

    tech_effective_hours = fields.Float(
        string="Technician Effective Hours", readonly=True, aggregator="sum"
    )
    tech_allocated_hours = fields.Float(
        string="Technician Planned Hours", readonly=True, aggregator="sum"
    )
    job_revenue = fields.Float(
        string="Job Revenue (Ordered, Pre-tax)", readonly=True, aggregator="sum"
    )
    tech_revenue = fields.Float(
        string="Technician Revenue (Allocated)", readonly=True, aggregator="sum"
    )
    tech_revenue_per_hour = fields.Float(
        string="Avg Technician Revenue per Hour",
        readonly=True,
        aggregator="avg",
    )

    def _select(self):
        return """
                MIN(aal.id) AS id,
                so.id AS sale_order_id,
                so.partner_id AS partner_id,
                so.date_order AS date_order,
                so.company_id AS company_id,
                aal.user_id AS user_id,
                aal.employee_id AS employee_id,
                COALESCE(SUM(aal.unit_amount), 0) AS tech_effective_hours,
                0.0 AS tech_allocated_hours,
                COALESCE(MAX(rev.job_revenue), 0) AS job_revenue,
                CASE
                    WHEN COALESCE(MAX(ht.total_effective_hours), 0) > 0 THEN
                        COALESCE(MAX(rev.job_revenue), 0)
                        * COALESCE(SUM(aal.unit_amount), 0)
                        / COALESCE(MAX(ht.total_effective_hours), 0)
                    ELSE 0
                END AS tech_revenue,
                CASE
                    WHEN COALESCE(SUM(aal.unit_amount), 0) > 0
                         AND COALESCE(MAX(ht.total_effective_hours), 0) > 0 THEN
                        (COALESCE(MAX(rev.job_revenue), 0)
                         * COALESCE(SUM(aal.unit_amount), 0)
                         / COALESCE(MAX(ht.total_effective_hours), 0))
                        / COALESCE(SUM(aal.unit_amount), 0)
                    ELSE 0
                END AS tech_revenue_per_hour
        """

    def _from(self):
        return """
                account_analytic_line aal
                JOIN project_task t
                    ON aal.task_id = t.id
                JOIN sale_order so
                    ON t.sale_order_id = so.id
                LEFT JOIN (
                    SELECT
                        so2.id AS sale_order_id,
                        COALESCE(SUM(
                            CASE
                                WHEN pc.is_fsm_product THEN sol2.price_subtotal
                                ELSE 0
                            END
                        ), 0) AS job_revenue
                      FROM sale_order so2
                      LEFT JOIN sale_order_line sol2
                        ON sol2.order_id = so2.id
                      LEFT JOIN product_product pp
                        ON sol2.product_id = pp.id
                      LEFT JOIN product_template pt
                        ON pp.product_tmpl_id = pt.id
                      LEFT JOIN product_category pc
                        ON pc.id = pt.categ_id
                  GROUP BY so2.id
                ) AS rev
                    ON rev.sale_order_id = so.id
                LEFT JOIN (
                    SELECT
                        t2.sale_order_id AS sale_order_id,
                        COALESCE(SUM(aal2.unit_amount), 0) AS total_effective_hours
                      FROM account_analytic_line aal2
                      JOIN project_task t2
                        ON aal2.task_id = t2.id
                  GROUP BY t2.sale_order_id
                ) AS ht
                    ON ht.sale_order_id = so.id
        """

    def _group_by(self):
        return """
                so.id,
                so.partner_id,
                so.date_order,
                so.company_id,
                aal.user_id,
                aal.employee_id
        """

    def _where(self):
        # is_fsm is computed: True if any order line has a service product with
        # service_tracking = 'task_global_project'
        return """
                EXISTS (
                    SELECT 1
                      FROM sale_order_line sol
                      JOIN product_product pp ON sol.product_id = pp.id
                      JOIN product_template pt ON pp.product_tmpl_id = pt.id
                     WHERE sol.order_id = so.id
                       AND pt.type = 'service'
                       AND pt.service_tracking = 'task_global_project'
                )
                AND aal.unit_amount IS NOT NULL
        """

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(
            f"""
            CREATE VIEW {self._table} AS
                SELECT {self._select()}
                  FROM {self._from()}
                 WHERE {self._where()}
              GROUP BY {self._group_by()}
            """
        )
