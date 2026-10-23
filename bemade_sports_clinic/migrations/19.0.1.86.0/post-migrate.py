"""Review fixes 2026-10-18 — injury dates rule.

A resolved injury carries no predicted resolution date any more (the model
clears it on every resolve from now on). This nulls it on the injuries that
were already resolved, in SQL: no tracking value, no chatter message, no
digest bump. Unresolved injuries — including those that carry a resolution
date — are not touched. The logic is
``sports.patient.injury._sc_clear_resolved_predicted_dates``.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cleared = env['sports.patient.injury']._sc_clear_resolved_predicted_dates()
    _logger.info("Review fixes 1018: predicted resolution date cleared on %s resolved injury(ies).",
                 cleared)
