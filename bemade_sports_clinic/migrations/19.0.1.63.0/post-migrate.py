"""Task 1601 — seed the training recommendation history from mail tracking.

Every ``mail.tracking.value`` of ``sports.patient.training_recommendation``
becomes one ``sports.patient.training.history`` row (message date, author
partner's user else the message creator, the new text). Deleted players are
skipped; players that already have history rows are skipped (idempotent). A
current recommendation with no tracking gets NO synthetic row (no stamp).
The logic is ``sports.patient.training.history._backfill_from_tracking``.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    created = env['sports.patient.training.history']._backfill_from_tracking()
    _logger.info("Task 1601: %s training recommendation history row(s) seeded.", created)
