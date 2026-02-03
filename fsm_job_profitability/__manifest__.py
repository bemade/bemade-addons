{
    "name": "FSM Job Profitability",
    "summary": "FSM job profitability analysis (revenue per hour, margin, KPIs) for field service projects",
    "version": "18.0.1.0.1",
    "author": "Bemade Inc.",
    "license": "LGPL-3",
    "website": "https://www.bemade.org",
    "category": "Services/Field Service",
    "depends": [
        "project",
        "hr_timesheet",
        "hr_hourly_cost",
        "sale_project",
        "sale_timesheet",
        "industry_fsm",
        "industry_fsm_sale",
        "fsm_product_category_flag",
    ],
    "description": """
FSM Job Profitability
=====================

This module adds read-only job profitability reporting for Field Service (FSM)
engagements.

Key features
------------

Job-level profitability (model ``report.fsm.job``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- One row per FSM sale order / job.
- Revenue basis: ordered, pre-tax amount from related sale order lines.
- Revenue filtering: only products whose category is flagged as FSM Product
  (boolean ``product.category.is_fsm_product`` from addon
  ``fsm_product_category_flag``).
- Time basis: effective hours coming from FSM tasks linked to the sale order.
- Measures include ``job_revenue``, ``job_effective_hours`` and
  ``job_revenue_per_hour``.

Technician-level profitability (model ``report.fsm.tech.job``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- One row per (FSM sale order, technician) pair.
- Hours source: timesheets (``account.analytic.line``) linked to FSM tasks.
- Revenue allocation: job revenue is allocated to technicians proportionally
  to their share of effective hours on the job.
- Measures include technician effective hours, allocated revenue, job revenue
  (for reconciliation), and average technician revenue per hour.

Read-only reporting
~~~~~~~~~~~~~~~~~~~

- Implemented via SQL views only; the module does not create or modify
  accounting entries.
- Metrics are derived from existing Odoo objects such as ``project.task``,
  ``sale.order``, ``sale.order.line`` and ``account.analytic.line``.

Intended usage
--------------

- Analyze revenue and time spent per job, and how revenue is attributed to
  technicians, without changing core FSM or accounting behavior.
- Export results to spreadsheets or dashboards for further KPI analysis.

Prerequisites & data quality
----------------------------

- FSM jobs (top-level FSM tasks) should be linked to the relevant sales order
  and/or sales order line so revenue attribution makes sense.
- Planned hours should be reasonably maintained to compare planned vs actual.
- Backorders or split work should preserve links to the original job scope.
- Timesheet practices should be consistent with how allocations are defined.
""",
    "data": [
        "security/ir.model.access.csv",
        "report/project_report_views.xml",
        "report/tech_report_views.xml",
    ],
    "installable": True,
    "application": False,
}
