# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5345 (kit P3c2): the user menu popup and thirteen shell components
moved to the kit (``ADOPTED_VIEWS``: ``sc_user_menu_popup``,
``sc_list_header``, ``sc_card_icons``, ``sc_history_entry``,
``sc_history_list``, ``sc_banner``, ``sc_flash_banners``, ``sc_switch``,
``sc_confirm_sheet``, ``sc_link_row``, ``sc_row_links``, ``sc_entity_row``,
``sc_field_static``, ``sc_return_overdue_flag`` -> ``pk_*``), and
``sc_app_layout`` now calls the kit's new ``pk_app_layout``.

Same reason as 19.0.1.141.0 to 19.0.1.144.0: ``-u bemade_sports_clinic``
alone does not upgrade the kit, and the clinic's data no longer declares
these views, so its upgrade would delete them. The idempotent helper adopts
them (a no-op when the kit's install hook or pre-migration did it first);
when the kit is not upgraded in this run, the kit's view files are loaded
(the adopted views take the kit's arch, ``pk_app_layout`` exists before the
clinic's layout calls it) with the kit's translations of them.
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
