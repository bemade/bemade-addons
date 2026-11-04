# -*- coding: utf-8 -*-
"""19.0.3.0.0 — traces gain a validation gate (``validated``, ``validated_by``,
``validated_at``) and ``submitted_by`` gains ``resource``; deliverables and the reading
log are new tables (nothing to migrate for them).

Every trace that existed before this version was entered by the parent, whether it says
``submitted_by = parent`` or was typed on the student's behalf: nothing was ever submitted
through a portal, so nothing is pending. The ORM fills the new ``validated`` column with
its default (True) when it adds it; this script makes the parent traces explicitly
validated in case the column was created without the default (an interrupted upgrade, a
manual ``ALTER``). Idempotent: only rows still NULL or false are touched.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        "UPDATE homeschool_trace SET validated = TRUE "
        "WHERE submitted_by = 'parent' AND (validated IS NULL OR validated = FALSE)"
    )
    _logger.info("homeschool: %d parent traces marked validated", cr.rowcount)
