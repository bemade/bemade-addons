# -*- coding: utf-8 -*-
"""19.0.2.0.0 — one instance, several families: every family-owned row gets a company.

Rows created before this version have no ``company_id``; they all belong to the family
that ran the instance alone, i.e. the main company. Blocks and journal entries take the
company of their day. Idempotent: only NULL values are touched, so re-running is a no-op.
The record rules live in ``security/homeschool_rules.xml`` (not noupdate) and refresh
with the module data; nothing to migrate there.
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


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    main_company = env.ref("base.main_company")
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
