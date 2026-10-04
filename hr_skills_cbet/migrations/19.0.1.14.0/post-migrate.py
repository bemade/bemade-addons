"""Stamp every competency with its current content fingerprint.

The import guard (19.0.1.14.0) skips a competency whose content no longer
matches the fingerprint stamped by its last import. The content in the database
at upgrade time IS the last import, so it becomes the baseline: re-importing the
same archive afterwards skips and changes nothing, and any edit made in Odoo
from now on is detected.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

BATCH = 100


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    competencies = env["cbet.competency"].with_context(active_test=False).search([])
    for start in range(0, len(competencies), BATCH):
        batch = competencies[start:start + BATCH]
        batch._stamp_import()
        env.flush_all()
        env.invalidate_all()
    _logger.info("hr_skills_cbet: stamped the import fingerprint of %s competencies",
                 len(competencies))
