FSM Job Profitability
=====================

Overview
--------

``fsm_job_profitability`` provides **read-only job profitability analysis**
for Field Service (FSM) engagements. It leverages existing project, timesheet
and sales data to expose actionable KPIs at both **job** (sale order) and
**technician** levels, without creating any accounting entries.

Implemented Features
--------------------

Read-only reporting layer
~~~~~~~~~~~~~~~~~~~~~~~~~

- No accounting postings; all data comes from existing Odoo models:
  ``project.task``, ``sale.order``, ``sale.order.line``,
  ``account.analytic_line`` and FSM-related extensions.
- Implemented entirely as SQL views, exposed through pivot and graph views
  under Field Service → Reporting.

Job-level FSM profitability (``report.fsm.job``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Grain: one row per FSM sale order / job.
- Revenue basis: ordered, pre-tax amount from related sale order lines.
- FSM revenue filtering:

  - Only lines whose product categories are flagged as FSM products via the
    companion addon ``fsm_product_category_flag``
    (boolean ``product.category.is_fsm_product``) are included.
  - If no categories are flagged for a company, the report falls back to the
    full sale order untaxed amount.

- Time basis: effective hours aggregated from FSM tasks linked to the sale
  order.
- Core indicators:

  - ``job_revenue`` (FSM revenue for the job).
  - ``job_effective_hours`` (sum of effective hours on linked FSM tasks).
  - ``job_revenue_per_hour`` with safe division-by-zero handling.
    In pivot views this is exposed as an *average* ratio; sums of revenue
    and hours remain the authoritative basis for further analysis.

- Reporting UX:

  - Pivot and graph views accessible from Field Service → Reporting →
    *Job Profitability*.
  - Grouping by customer, sales order, order date and other common
    dimensions.

Technician-level FSM profitability (``report.fsm.tech.job``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Grain: one row per **(FSM sale order, technician)** pair.
- Hours source:

  - Timesheet lines (``account.analytic_line``) linked to FSM tasks.
  - Grouped by ``user_id`` (Odoo user) and optionally ``employee_id``
    (HR employee).

- Revenue allocation:

  - Each job’s FSM revenue (as defined above) is allocated to technicians
    **proportionally to their share of effective hours** on that job.

- Core indicators:

  - Technician effective hours on the job.
  - Allocated job revenue per technician.
  - Job revenue (for reconciliation with the job-level report).

- Reporting UX:

  - Dedicated pivot and graph action under Field Service → Reporting →
    *Technician Profitability*.
  - Useful group-bys: technician (user/employee), customer, sales order,
    order month, etc.

Security and access
~~~~~~~~~~~~~~~~~~~

- Both models are read-only SQL views.
- Access is granted to Field Service managers and users via ACLs on
  ``report.fsm.job`` and ``report.fsm.tech.job`` (using FSM groups from
  the `[industry_fsm](cci:7://file:///Users/ddurepos/src/durpro-18/enterprise/industry_fsm:0:0-0:0)` module).

Prerequisites & Data Quality Expectations
-----------------------------------------

The module assumes certain data hygiene in your FSM / sales / timesheet
processes to produce meaningful results:

- FSM jobs (top-level FSM tasks) should be properly linked to the relevant
  sales order / sales order line so that revenue attribution makes sense.
- Allocated / planned hours on FSM jobs should be reasonably maintained,
  so comparisons against actual timesheet effort are meaningful.
- When using service backorders or splitting work across multiple FSM tasks,
  links to the original job scope (sale order / sale order line) should be
  preserved.
- Timesheet practices (e.g. whether to include prep and travel time) should
  be consistent with how job allocations are defined.
- Product categories used for FSM services should be flagged correctly via
  ``fsm_product_category_flag`` so that revenue filtering behaves as
  expected.

Backlog / Future Enhancements
-----------------------------

The following items were considered in early design discussions but are
**not implemented in v1**. They remain candidates for future work:

Task- and project-level profitability fields
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Adding read-only profitability fields on:

  - ``project.task`` forms for FSM tasks.
  - ``project.project`` for FSM projects.

- Examples: ``fsm_revenue``, ``fsm_revenue_per_hour``, and margin fields.

Extending existing FSM analysis views
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Injecting profitability fields directly into
  ``report.project.task.user.fsm``-based analysis views, instead of relying
  solely on the separate SQL reporting models.

Advanced filters and audit-style reports
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Predefined filters such as “Unprofitable jobs” or “Low revenue per hour”.
- Audit lists for:

  - Jobs still open long after their planned start/visit date.
  - Jobs closed without any related timesheets.
  - Jobs with large variance between planned and actual hours.

Configurable revenue basis and tax handling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Company-level settings to choose:

  - Ordered vs delivered vs invoiced revenue.
  - Whether to include taxes.

Cost and margin analysis
~~~~~~~~~~~~~~~~~~~~~~~~

- Integration with employee cost (``hr_hourly_cost`` / analytic costs) to
  compute:

  - Technician and job-level cost.
  - Gross margin and margin rate KPIs.

Project-level aggregates and dashboards
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Higher-level aggregates across projects / customers, and dedicated
  dashboard-style views or spreadsheets built on top of the SQL views.

Stronger process enforcement and tooling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Additional tooling or constraints to improve data quality, for example:

  - Ensuring all FSM jobs have proper SO / SO-line links and reasonable
    allocated hours.
  - More automation around backorders and job templates.

For now, this module focuses on providing reliable, read-only KPIs that
can feed spreadsheets, dashboards and further custom reporting.
```~~