"""Task 1666 — the clinic emails are signed « Le Fit Crew ».

The mail templates are updatable, so their English subjects follow the data
file; but the event-cancelled subject also carries a French translation
(« Événement annulé : … ») that an upgrade keeps (a module update never
overwrites an existing translation). Reload this module's French terms with
overwrite so it becomes « Le Fit Crew — Événement annulé : … ». Idempotent;
only the terms this module ships are touched.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    langs = [code for code, _name in env['res.lang'].get_installed() if code.startswith('fr')]
    if not langs:
        return
    env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], langs, overwrite=True)
    _logger.info("Task 1666: bemade_sports_clinic French terms reloaded with overwrite (%s)",
                 ', '.join(langs))
