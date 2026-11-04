"""Task 1661 — fr_CA corrections reach existing databases.

A module upgrade loads the module's .po WITHOUT overwriting a term that
already has a translation (``--i18n-overwrite`` is not used by the deploy),
so a corrected msgstr (« Fin du thérapeute » → « Fin de la couverture »,
« Actif » → « Active », « Docteur » → « Médecin », …) would never replace
the old French in views, selection labels and menus. Reload this module's
French terms with overwrite. Only the terms this module ships are touched
(an empty msgstr is skipped; noupdate records keep their translations).
Python / JS strings need nothing: they are read from the .po at runtime.
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
    _logger.info("Task 1661: bemade_sports_clinic French terms reloaded with overwrite (%s)",
                 ', '.join(langs))
