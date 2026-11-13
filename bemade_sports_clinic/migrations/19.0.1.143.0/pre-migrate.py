# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5381 (kit P4c2): the edit card head, the display row, the sheet and
the page tabs moved to the kit (``sc_edit_card_head`` ->
``bemade_portal_kit.pk_edit_card_head``, ``sc_display_row`` ->
``pk_display_row``, ``sc_sheet`` -> ``pk_sheet``, ``sc_page_tabs`` ->
``pk_page_tabs``; ``ADOPTED_VIEWS``).

Same reason as 19.0.1.141.0 / 19.0.1.142.0: ``-u bemade_sports_clinic``
alone does not upgrade the kit, and the clinic's data no longer declares
these views, so its upgrade would delete them. The idempotent helper adopts
them (a no-op when the kit's install hook or pre-migration did it first);
when the kit is not upgraded in this run, the kit's view files are loaded
(the adopted views take the kit's arch) with the kit's translations of them.
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
