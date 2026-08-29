"""Score duplicate groups proposed before similarity was recorded.

Without this they read 0% forever: a re-scan will not rescore them, because
the scan deliberately skips clusters it has already grouped. The score is what
makes the review queue rankable, so a queue full of zeroes is a queue nobody
can triage.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    targets = env["bemade.dedup.target"].with_context(active_test=False).search([])
    if not targets:
        return
    _logger.info("backfilling deduplication similarity on %s target(s)", len(targets))
    targets._backfill_similarity()
