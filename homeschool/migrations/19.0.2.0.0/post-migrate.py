# -*- coding: utf-8 -*-
"""19.0.2.0.0 — one instance, several families: every family-owned row gets a company,
and the coverage of the curriculum becomes per family.

Rows created before this version have no ``company_id``; they all belong to the family
that ran the instance alone, i.e. the main company. Blocks and journal entries take the
company of their day. Idempotent: only NULL values are touched, so re-running is a no-op.
The record rules live in ``security/homeschool_rules.xml`` (not noupdate) and refresh
with the module data; nothing to migrate there.

Coverage: the item-level columns (``coverage_override``, ``coverage_note``,
``coverage_date`` and the stored computed ``coverage_status``, ``coverage_computed``,
``trace_count``, ``block_count``, ``last_evidence_date``) become non-stored fields
delegating to a ``homeschool.item.coverage`` row per (item, company). One row per item is
created for the main company from the old manual columns (the computed values are
recomputed from the main company's traces and blocks by the ORM), then the old columns
are dropped. Idempotent: the second run finds no old columns and does nothing.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

OWN_COMPANY_TABLES = (
    "homeschool_student",
    "homeschool_year",
    "homeschool_day",
    "homeschool_trace",
    "homeschool_review",
    "homeschool_project",
    "homeschool_material",
    "homeschool_block_template",
    "homeschool_indicator",
    "homeschool_indicator_value",
)
FROM_DAY_TABLES = ("homeschool_block", "homeschool_journal")

# the former item-level coverage columns; the first three are data, the rest were stored computes
OLD_ITEM_COVERAGE_COLUMNS = (
    "coverage_override", "coverage_note", "coverage_date",
    "coverage_status", "coverage_computed", "trace_count", "block_count", "last_evidence_date",
)


def _backfill_company(cr, main_company):
    for table in OWN_COMPANY_TABLES:
        cr.execute(
            "UPDATE %s SET company_id = %%s WHERE company_id IS NULL" % table,  # noqa: S608 (table from a constant tuple)
            (main_company.id,),
        )
        if cr.rowcount:
            _logger.info("homeschool: %s: %d rows moved to company %s", table, cr.rowcount, main_company.name)
    for table in FROM_DAY_TABLES:
        cr.execute(
            "UPDATE %s t SET company_id = d.company_id FROM homeschool_day d "
            "WHERE t.day_id = d.id AND t.company_id IS NULL" % table,  # noqa: S608
        )
        if cr.rowcount:
            _logger.info("homeschool: %s: %d rows took their day's company", table, cr.rowcount)


def _coverage_per_family(cr, env, main_company):
    cr.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'homeschool_item' AND column_name IN %s",
        (OLD_ITEM_COVERAGE_COLUMNS,),
    )
    old_columns = {row[0] for row in cr.fetchall()}
    if not old_columns:
        return  # already migrated
    manual = [c for c in ("coverage_override", "coverage_note", "coverage_date") if c in old_columns]
    Coverage = env["homeschool.item.coverage"]
    existing = set(Coverage.search([("company_id", "=", main_company.id)]).item_id.ids)
    cr.execute("SELECT id, %s FROM homeschool_item ORDER BY id" % ", ".join(manual or ["NULL"]))  # noqa: S608 (constant column names)
    vals_list = []
    for row in cr.fetchall():
        item_id, values = row[0], dict(zip(manual, row[1:]))
        if item_id in existing:
            continue
        vals_list.append({
            "item_id": item_id, "company_id": main_company.id,
            "override": values.get("coverage_override") or False,
            "note": values.get("coverage_note") or False,
            "date": values.get("coverage_date") or False,
        })
    if vals_list:
        Coverage.create(vals_list)
        env.flush_all()
    _logger.info("homeschool: item coverage: %d rows created for company %s (%d already there)",
                 len(vals_list), main_company.name, len(existing))
    for column in sorted(old_columns):
        cr.execute("ALTER TABLE homeschool_item DROP COLUMN IF EXISTS %s" % column)  # noqa: S608 (constant column names)
    _logger.info("homeschool: item coverage: dropped the item-level columns %s", ", ".join(sorted(old_columns)))


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    main_company = env.ref("base.main_company")
    _backfill_company(cr, main_company)
    _coverage_per_family(cr, env, main_company)
