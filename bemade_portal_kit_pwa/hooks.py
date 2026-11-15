# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Install hook: adopt the first consumer's install and offline templates
before this addon's data is loaded (``tools/adopt.py``). Plain SQL; a
no-op on a database without that consumer."""
from odoo.addons.bemade_portal_kit.tools.adopt import adopt_views

from .tools.adopt import PWA, PWA_ADOPTED_VIEWS


def pre_init_hook(env):
    adopt_views(env.cr, PWA_ADOPTED_VIEWS, target=PWA)
