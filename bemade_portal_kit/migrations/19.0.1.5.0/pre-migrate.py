# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5369 (kit P3c1): the kit adopts the clinic's icon and first
components (``tools/adopt.py``, ``ADOPTED_VIEWS``).

Runs BEFORE the kit's data is loaded: the clinic's views take the kit's
external ids, so ``views/pk_layout.xml`` and ``views/pk_components.xml``
update the same records (same ids, inheriting views and translations kept)
instead of creating new ones. The clinic's own pre-migration (19.0.1.139.0)
calls the same helper, for an upgrade of the clinic alone (which does not
upgrade the kit); whichever runs first adopts, the other finds nothing to do.
"""
from odoo.addons.bemade_portal_kit.tools.adopt import adopt_views


def migrate(cr, version):
    adopt_views(cr)
