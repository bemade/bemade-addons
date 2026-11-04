"""Review round 2 (owner 2026-10-27) — French wording an upgrade alone
would not apply.

#1725's hint now ends « … ouvrez l'événement concerné : » followed by the
link « Mes événements sans feuilles de temps » (same for the empty line). A
module update never overwrites an existing translation, and the view
update carries the OLD French over to the reworded English term (« … »
ending with a period), so this module's French files are reloaded with
overwrite (#1661/#1666/#1678 pattern). Idempotent; only the terms this
module ships are touched.
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
    _logger.info("Review round 2: bemade_sports_clinic French terms reloaded with overwrite (%s)",
                 ', '.join(langs))
