"""Task 1628 — incomplete-player To-Dos cover NEW players only.

Sets the cut-off ``bemade_sports_clinic.incomplete_todo_since`` to the
upgrade time, so the daily cron only sweeps players created from now on (no
backfill of the existing files; the past backlog is task 1632). An already
set cut-off is left as is.
"""
import logging

from odoo import SUPERUSER_ID, api, fields

_logger = logging.getLogger(__name__)

PARAM = 'bemade_sports_clinic.incomplete_todo_since'


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    ICP = env['ir.config_parameter'].sudo()
    if ICP.get_param(PARAM):
        _logger.info("Task 1628: cut-off %s already set (%s), left as is.",
                     PARAM, ICP.get_param(PARAM))
        return
    now = fields.Datetime.to_string(fields.Datetime.now())
    ICP.set_param(PARAM, now)
    _logger.info("Task 1628: incomplete-player To-Do cut-off %s set to %s (UTC).", PARAM, now)
