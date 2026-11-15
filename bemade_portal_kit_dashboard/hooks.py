# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Install hook: adopt the first consumer's dashboard templates and move its
layout column before this addon's models and data are loaded
(``tools/adopt.py``). Plain SQL; a no-op on a database without that
consumer.

Task 5388: the kit's version is checked first (``require_kit``), so an
upgrade that would install this addon over an older kit stops before
anything is written."""
from odoo.addons.bemade_portal_kit.tools.version_guard import require_kit

from .tools.adopt import DASH, adopt_dashboard


def pre_init_hook(env):
    require_kit(env.cr, caller=DASH)
    adopt_dashboard(env.cr)
