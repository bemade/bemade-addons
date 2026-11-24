# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5371 (kit P4c1): the shell layout calls the kit's new toast host
(``bemade_portal_kit.pk_toast_host``, kit 19.0.1.8.0).

Same reason as 19.0.1.141.0: ``-u bemade_sports_clinic`` alone does not
upgrade the kit, so a database whose kit is still at 1.7.0 would have no
``pk_toast_host`` view and every shell page would fail to render. The kit's
view files are loaded when the kit is not upgraded in this run (with the
kit's translations of them, for the languages installed); the adoption
helper runs too (a no-op when nothing is left to adopt).
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
