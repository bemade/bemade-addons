# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5382 (kit P4c3): the autosave field moved to the kit
(``sc_field_autosave`` -> ``bemade_portal_kit.pk_field_autosave``;
``ADOPTED_VIEWS``).

Same reason as 19.0.1.141.0 to 19.0.1.143.0: ``-u bemade_sports_clinic``
alone does not upgrade the kit, and the clinic's data no longer declares
this view, so its upgrade would delete it. The idempotent helper adopts it
(a no-op when the kit's install hook or pre-migration did it first); when
the kit is not upgraded in this run, the kit's view files are loaded (the
adopted view takes the kit's arch) with the kit's translations of them.
"""
from odoo import SUPERUSER_ID, api

from odoo.addons.bemade_portal_kit.tools.adopt import KIT, adopt_views, load_kit_views


def migrate(cr, version):
    adopt_views(cr)
    env = api.Environment(cr, SUPERUSER_ID, {})
    if load_kit_views(env):
        langs = [code for code, _name in env['res.lang'].get_installed() if code != 'en_US']
        if langs:
            env['ir.module.module']._load_module_terms([KIT], langs)
