# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5200 (kit P5): « Plus », « Paramètres », « Mon compte »,
« Sécurité », the search sheet and the calendar moved to the kit
(``ADOPTED_VIEWS``), with the clinic's stored data
(``tools/data_moves.py``): the user columns ``sc_theme`` /
``sc_show_done_buttons`` (-> ``pk_theme`` / ``pk_show_done_buttons``, every
user's value kept), the parameters ``app_shell_enabled``,
``sc_theme_choice_enabled`` and ``help_home_url`` (-> ``bemade_portal_kit.*``;
an absent one stays absent) and the help mapping ``sc.help.article`` (->
``portal.kit.help``, the same rows).

``-u bemade_sports_clinic`` alone does not upgrade the kit, and it
re-initialises ``res.users`` from the code, which declares the kit's fields:
the moves must happen HERE, before that, or the new columns are created
empty. The idempotent helpers are a no-op when the kit's install hook or
pre-migration did the work first. When the kit is not upgraded in this run,
its view files are loaded with their terms (as 19.0.1.145.0).
"""
from odoo import SUPERUSER_ID, api

from odoo.addons.bemade_portal_kit.tools.adopt import KIT, adopt_views, load_kit_views
from odoo.addons.bemade_portal_kit.tools.data_moves import move_data


def migrate(cr, version):
    adopt_views(cr)
    move_data(cr)
    env = api.Environment(cr, SUPERUSER_ID, {})
    if load_kit_views(env):
        langs = [code for code, _name in env['res.lang'].get_installed() if code != 'en_US']
        if langs:
            env['ir.module.module']._load_module_terms([KIT], langs)
