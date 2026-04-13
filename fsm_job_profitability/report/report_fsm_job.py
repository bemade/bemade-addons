# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, tools


class ReportFsmJob(models.Model):
    """FSM Job-level profitability analysis.

    Grain: one row per sale order (job). Revenue comes from the sale order's
    untaxed amount, and hours are aggregated from linked FSM tasks via the
    existing report.project.task.user.fsm view.
    """

    _name = 'report.fsm.job'
    _description = 'FSM Job Profitability'
    _auto = False

    sale_order_id = fields.Many2one('sale.order', string='Sales Order', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    date_order = fields.Datetime(string='Order Date', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)

    job_effective_hours = fields.Float(string='Effective Hours', readonly=True, aggregator='sum')
    job_allocated_hours = fields.Float(string='Planned Hours', readonly=True, aggregator='sum')
    job_revenue = fields.Float(string='Job Revenue (Ordered, Pre-tax)', readonly=True, aggregator='sum')
    job_revenue_per_hour = fields.Float(
        string='Avg Job Revenue per Hour',
        readonly=True,
        aggregator='avg',
    )

    def _select(self):
        return """
                so.id AS id,
                so.id AS sale_order_id,
                so.partner_id AS partner_id,
                so.date_order AS date_order,
                so.company_id AS company_id,
                COALESCE(SUM(ft.effective_hours), 0) AS job_effective_hours,
                COALESCE(SUM(ft.allocated_hours), 0) AS job_allocated_hours,
                COALESCE(MAX(rev.job_revenue), 0) AS job_revenue,
                CASE
                    WHEN COALESCE(SUM(ft.effective_hours), 0) > 0 THEN
                        COALESCE(MAX(rev.job_revenue), 0) / SUM(ft.effective_hours)
                    ELSE 0
                END AS job_revenue_per_hour
        """

    def _from(self):
        return """
                sale_order so
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
                LEFT JOIN report_project_task_user_fsm ft
                    ON ft.sale_order_id = so.id
        """

    def _group_by(self):
        return """
                so.id,
                so.partner_id,
                so.date_order,
                so.company_id,
                so.amount_untaxed
        """

    def _where(self):
        # Restrict to orders that have at least one linked FSM task entry.
        return """
                ft.id IS NOT NULL
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
