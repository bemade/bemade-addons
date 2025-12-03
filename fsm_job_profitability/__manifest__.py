{
    'name': 'FSM Job Profitability',
    'summary': 'FSM job profitability analysis (revenue per hour, margin, KPIs) for field service projects',
    'version': '18.0.1.0.0',
    'author': 'Bemade Inc.',
    'license': 'LGPL-3',
    'website': 'https://www.bemade.org',
    'category': 'Services/Field Service',
    'depends': [
        'project',
        'hr_timesheet',
        'hr_hourly_cost',
        'sale_project',
        'sale_timesheet',
        'industry_fsm',
        'industry_fsm_sale',
        'fsm_product_category_flag',
    ],
    'description': '''
FSM Job Profitability
=====================

This module adds **read-only job profitability analysis** for Field Service (FSM)
engagements. It leverages existing project, timesheet and sales data to expose
actionable KPIs at both **job** (sale order) and **technician** levels.

Key features
------------

- **Job-level FSM profitability** (model ``report.fsm.job``)
  - One row per FSM sale order / job.
  - Revenue basis: ordered, pre-tax amount from related sale order lines.
  - Revenue is filtered to **FSM service products only**, using the
    ``fsm_product_category_flag`` addon (boolean ``product.category.is_fsm_product``).
  - Time basis: effective hours coming from FSM tasks linked to the sale order.
  - Exposes indicators such as:
    - ``job_revenue`` (FSM revenue on the job)
    - ``job_effective_hours``
    - ``job_revenue_per_hour`` (with safe zero-division handling)
  - Pivot / graph views under Field Service → Reporting allow aggregation by
    customer, project, date, etc.

- **Technician-level FSM profitability** (model ``report.fsm.tech.job``)
  - One row per **(FSM sale order, technician)** pair.
  - Uses ``account.analytic.line`` timesheet entries linked to FSM tasks to get
    the real effective hours per technician.
  - Allocates each job's FSM revenue to technicians **proportionally to their
    share of effective hours** on that job.
  - Provides measures such as:
    - Technician effective hours on the job
    - Allocated job revenue per technician
    - Job revenue (for reconciliation)
  - A dedicated pivot/graph action (Field Service → Reporting → Technician
    Profitability) lets managers analyze performance by user/employee,
    customer, job, or period.

- **Read-only reporting, no postings**
  - Implemented via SQL views only; the module does not create or modify
    accounting entries.
  - All metrics are derived from existing Odoo objects:
    ``project.task``, ``sale.order``, ``sale.order.line``,
    ``account.analytic.line``, and related FSM models.

Intended usage
--------------

- Give FSM managers a clear view of **revenue and time spent per job** and
  **which technicians generated that revenue**, without changing core FSM or
  accounting behavior.
- Serve as a reporting layer that can be exported to spreadsheets or dashboards
  for further KPI and margin analysis.

Prerequisites & data quality
----------------------------

- FSM jobs (top-level FSM tasks) should be properly linked to the relevant
  sales order / sales order line so that revenue attribution makes sense.
- Allocated / planned hours on FSM jobs should be reasonably maintained to
  make comparisons against actual timesheet effort meaningful.
- When using service backorders or splitting work across multiple FSM tasks,
  links to the original job scope (sale order / sale order line) should be
  preserved.
- Timesheet practices (e.g., whether to include prep and travel time) should
  be consistent with how job allocations are defined.
''',
    'data': [
        'security/ir.model.access.csv',
        'report/project_report_views.xml',
        'report/tech_report_views.xml',
    ],
    'installable': True,
    'application': False,
}
