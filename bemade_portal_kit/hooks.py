# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Install hooks of the kit.

Task 5372: a database that has a consumer but not yet the kit (e.g. the
clinic at a version older than the kit) installs the kit as a new
dependency during the consumer's upgrade. An installed module runs no
migration scripts, so the kit's pre-migration (19.0.1.5.0) does not run
there; this hook adopts the consumer's views instead, before the kit's data
is loaded (``tools/adopt.py``). Plain SQL only: the kit's models do not
exist yet. A no-op on a database without a consumer.
"""
from .tools import adopt


def pre_init_hook(env):
    adopt.adopt_views(env.cr, adopt.ADOPTED_VIEWS)
