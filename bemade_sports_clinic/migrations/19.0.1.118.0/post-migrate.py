"""Task 1678 — French wording fixes that an upgrade alone would not apply.

A module update never overwrites an existing translation, so the corrected
French terms (removal request messages, « Personnel assigné », « Commentaire
(facultatif) ») and the morning-digest template's French body (still
« Annonce de l'équipe » on databases that stored the old text) are reloaded
from this module's French files with overwrite (#1661/#1666 pattern).
Idempotent; only the terms this module ships are touched.
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
    _logger.info("Task 1678: bemade_sports_clinic French terms reloaded with overwrite (%s)",
                 ', '.join(langs))
