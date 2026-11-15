# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Install hook: adopt the first consumer's dashboard templates and move its
layout column before this addon's models and data are loaded
(``tools/adopt.py``). Plain SQL; a no-op on a database without that
consumer."""
from .tools.adopt import adopt_dashboard


def pre_init_hook(env):
    adopt_dashboard(env.cr)
